# Simplify Entry to Plain Function

## Status
active (implement after remove-worker-class-v3)

## Prerequisites
- [ ] remove-worker-class-v3 complete

## Goal
Simplify entry points from toolsets to plain async functions. Entry points are trusted code that don't need toolset/approval machinery.

## Current Design (after v3)

```python
# Entry author writes:
def build_entry(ctx):
    toolset = FunctionToolset()

    @toolset.tool
    async def main(input: str, *, ctx) -> str:
        return await ctx.deps.call_agent(spec, input)

    return toolset

entry_spec = EntrySpec(
    toolset_spec=ToolsetSpec(factory=build_entry),
    name="my_entry",
)

# Runtime does:
scope = runtime.create_scope(entry_spec)  # instantiates toolset
result = await scope.call_tool("main", input)
await scope.close()
```

## Proposed Design

```python
# Entry author writes:
async def main(input: str, runtime: CallRuntime) -> str:
    return await runtime.call_agent(spec, input)

entry_spec = EntrySpec(
    main=main,
    name="my_entry",
)

# Runtime does:
call_runtime = runtime.spawn_call_runtime(model=NULL_MODEL, ...)
result = await entry_spec.main(normalized_input, call_runtime)
```

## What This Removes

1. `FunctionToolset` wrapper for entries
2. `@toolset.tool` decorator on entry main
3. `ToolsetSpec` in `EntrySpec`
4. `call_tool("main", ...)` indirection
5. "exactly one tool named main" validation
6. `CallScope` for entry (agents still use it for their toolsets)

## Changes

### EntrySpec (simplified)

```python
@dataclass
class EntrySpec:
    main: Callable[[Any, CallRuntime], Awaitable[Any]]
    name: str
    description: str | None = None
    schema_in: type[WorkerArgs] | None = None
```

### Runtime.run_entry() (simplified)

```python
async def run_entry(self, entry_spec: EntrySpec, input_data: Any) -> Any:
    # Normalize input
    normalized = normalize_input(entry_spec.schema_in, input_data)

    # Emit event
    if self.config.on_event:
        self.config.on_event(UserMessageEvent(...))

    # Create runtime for this call (no toolsets - entry doesn't need them)
    call_runtime = self.spawn_call_runtime(
        active_toolsets=[],
        model=NULL_MODEL,
        invocation_name=entry_spec.name,
        depth=0,
    )

    # Call entry function directly
    return await entry_spec.main(normalized, call_runtime)
```

### Runtime.create_scope() — Remove or repurpose

With this simplification, `create_scope()` is only needed for multi-turn chat mode (where we want to preserve the runtime across turns). Consider:
- Remove `create_scope()` entirely, or
- Keep it but it returns `CallRuntime` directly (no CallScope wrapper for entries)

### agent_as_toolset — Still needed

Still required for exposing agents as tools to OTHER agents. Root entry doesn't use it.

## Discovery: How the Runner Finds the Entry (Decision: Explicit ENTRY)

```python
# my_entry.py
async def main(input_data, runtime):
    return await runtime.call_agent(spec, input_data)

# Explicit export - loader looks for EntrySpec instances
ENTRY = EntrySpec(main=main, name="my_entry", schema_in=MyArgs)
```

Discovery: scan module for `EntrySpec` instances (same as v3, just different EntrySpec shape).

For `.worker` files, the loader creates `EntrySpec` from frontmatter — no change there.

## Tasks

- [ ] Update `EntrySpec` to hold function reference instead of `ToolsetSpec`
- [ ] Update `Runtime.run_entry()` to call function directly
- [ ] Remove entry toolset validation ("exactly one main")
- [ ] Update loaders to produce function-based `EntrySpec`
- [ ] Update discovery to find `main` function or `EntrySpec` instance
- [ ] Decide fate of `Runtime.create_scope()` for chat mode
- [ ] Update tests and examples

## Decision: Entry main signature

Options:
1. `main(input: str, attachments: list[str] | None, runtime)` — explicit params
2. `main(args: WorkerArgs, runtime)` — structured input
3. `main(input_data: Any, runtime)` — generic (runtime normalizes)

Recommendation: Option 3 — keep normalization in `run_entry()`, pass result to main. Entry can type-hint the first param as needed.

## Rationale

Entry points are **trusted orchestration code**, not LLM-invoked tools. They don't need:
- Approval wrapping (that's for agent tools)
- Tool schema validation (explicit validation suffices)
- Toolset lifecycle management (they don't have toolsets)

The toolset wrapper adds complexity without benefit for this use case.
