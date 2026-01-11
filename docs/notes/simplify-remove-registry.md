# Simplify: Remove Unnecessary Abstractions from Registry Layer

## Problem

The current runtime has unnecessary abstractions layered on necessary orchestration:

1. **Invocable protocol** - an abstraction to unify Worker and ToolInvocable (only two cases)
2. **Worker as Toolset** - Worker inherits from AbstractToolset for packaging convenience
3. **Double discovery** - Workers found as both toolsets and entries with different naming

The orchestration work (toolset resolution, schema refs, overrides) is necessary. The abstractions on top are not.

## What the Registry Actually Does

The registry answers: "what can I run as an entry point?"

For **Python scripts that import and call directly**, no registry is needed - the script controls what it imports and calls.

But for **CLI invocation**, the registry still serves a purpose:
```bash
llm-do my_module.py --entry my_function
```

The CLI needs to:
1. Discover what's in the file (Workers + entry-capable functions)
2. Resolve `--entry name` to something runnable
3. Provide runtime context to Python functions (deps, call frames)

So the registry is the **CLI's view** of "what can I run?" - not a general abstraction.

### The Orchestration Problem

`build_invocable_registry()` does more than name mapping. It:
- Resolves toolsets (builtins, Python toolsets, worker references)
- Resolves schema refs
- Configures server-side tools (web_search, code_execution, etc.)
- Applies entry-specific overrides (model, --set flags)

If we remove the registry, this orchestration logic still needs to live somewhere. A `load_worker()` function would need to do the same wiring - it's effectively a registry builder with a different name.

**The problem isn't the orchestration** - that's necessary work. The problem is:
1. The `Invocable` abstraction layered on top
2. Worker inheriting from Toolset (causing double discovery)
3. The registry being treated as a core abstraction rather than CLI plumbing

## Simplify the Entry Protocol

Current `Invocable` unifies Worker and ToolInvocable under a `name + run()` contract.

The protocol itself is fine - but it can be simpler:

```python
class Entry(Protocol):
    name: str
    async def run(self, input_data: Any, run_ctx: RunContext[WorkerRuntime]) -> Any
```

- `Worker` implements `Entry` naturally
- Python functions become entries via a decorator

### Entry Toolset Scope (Code Entry)

`WorkerRuntime.call()` only searches `run_ctx.deps.toolsets`, which comes from the
entry object's `toolsets` field. ToolInvocable currently exposes *no toolsets*,
so code entry functions cannot delegate to other workers/tools via `ctx.call()`.

If ToolInvocable is removed, the replacement entry wrapper must carry toolsets.
Two options:
1. **Implicit scope**: registry injects all available toolsets into the entry wrapper.
2. **Explicit scope**: the decorator declares toolset names (recommended).

Explicit scope mirrors `.worker` files and keeps dependency boundaries visible.

Example (explicit scope):

```python
from llm_do.runtime import entry

@entry(toolsets=["pitch_evaluator", "filesystem_project"])
async def main(input_data: dict, ctx: WorkerRuntime) -> dict:
    report = await ctx.call("pitch_evaluator", {"input": input_data["query"]})
    files = await ctx.call("list_files", {"path": "."})
    return {"report": report, "files": files}
```

### Complete Example: Decorated Function Calling a Worker

```python
from llm_do.runtime import entry, load_worker

# Load worker at module level (or inside function)
analyst_worker = load_worker("analyst.worker")

@entry
async def orchestrator(input_data: dict, ctx: WorkerRuntime) -> dict:
    """Entry that delegates to a worker and post-processes results."""

    # Call the analyst worker
    analysis = await ctx.run(analyst_worker, {"input": input_data["query"]})

    # Call a tool directly
    files = await ctx.call("list_files", {"path": "."})
    # Or via proxy: files = await ctx.tools.list_files(path=".")

    # Combine results
    return {
        "analysis": analysis,
        "files": files,
        "summary": f"Analyzed query with {len(files)} context files"
    }
```

The decorator wraps the function to conform to `Entry`:
- `name` comes from the function name (or decorator arg)
- `run()` wraps the function, passing `run_ctx.deps` as `ctx`

This proves the abstraction is complete - a decorated function can do everything a Worker entry can:
- Receive input data
- Call other workers via `ctx.run()`
- Call tools via `ctx.call()` or `ctx.tools.*`
- Return results

No special `ToolInvocable` class needed - just a decorator.

## Why Worker-as-Toolset is Unnecessary

Worker inherits from AbstractToolset so you can add a Worker to another Worker's toolset list with the same API as other toolsets.

But this conflates two questions:
- "What can I execute as an entry?" (Worker as callable)
- "What tools does this agent have?" (Toolset as tool provider)

A Worker isn't a toolset that happens to be callable - it's a callable that can be *exposed as* a tool.

## Proposed Simplification

### Remove
- `Invocable` - replace with simpler `Entry` protocol
- `ToolInvocable` class - replace with `@entry` decorator
- Worker inheritance from AbstractToolset

### Rename/Simplify
- `InvocableRegistry` → `EntryRegistry` (or similar)
- `build_invocable_registry()` → keep orchestration, rename to reflect purpose

### Add
- `Entry` protocol - minimal interface (name + run)
- `@entry` decorator - makes a Python function conform to Entry
- `load_worker(path) -> Worker` - standalone function for direct Worker loading
- `WorkerToolset` adapter - wraps a Worker to expose it as a tool for another agent
- `EntryFunction` wrapper - holds resolved toolsets when `@entry(toolsets=[...])` is used

### New Flow

```python
# Direct Python usage (no registry):
worker = load_worker("main.worker")
await runtime.run(worker, input_data)

# CLI usage (registry for discovery):
registry = build_entry_registry(files, entry_name)
entry = registry.get(entry_name)  # Entry (Worker or decorated function)
await runtime.run(entry, input_data)  # uniform interface

# Python function as entry:
@entry(toolsets=["pitch_evaluator"])
async def analyze(input_data, runtime):
    ...

# Worker delegation (one worker calling another):
analyst = load_worker("analyst.worker")
main_worker = Worker(
    name="main",
    toolsets=[WorkerToolset(analyst), filesystem, ...],
    ...
)
```

### What Stays the Same
- Worker semantics (model selection, compatible_models, instructions)
- Toolset resolution (built-ins, Python toolsets, classpath loading)
- Runtime execution (approvals, events, depth tracking)

## Benefits

1. **Simpler protocol** - `Entry` is minimal (name + run), not over-engineered
2. **No wrapper class** - `@entry` decorator instead of `ToolInvocable`
3. **No double discovery** - Workers aren't discovered as both toolsets and entries
4. **Explicit delegation** - `WorkerToolset` makes "treating Worker as tool" explicit
5. **Direct Python usage** - `load_worker()` bypasses registry when not needed
6. **Uniform runtime interface** - `runtime.run(entry, ...)` works for all entries

## Compiler Analogy

This design maps cleanly to compiler/linker concepts (see also `docs/notes/toolsets-as-import-tables.md` and `docs/theory.md`):

| New Design | Compiler Analogy |
|------------|------------------|
| `Entry` protocol | Callable symbol interface (function signature) |
| `Worker` | Compiled module with entry point |
| `@entry` decorator | Symbol export directive (`pub`, `__declspec(dllexport)`) |
| `load_worker()` | Single-file compilation (parse + resolve → callable) |
| `WorkerToolset` adapter | Import stub / trampoline |
| `EntryRegistry` | Link-time symbol table |
| CLI | Linker (resolves entries across files) |
| Toolset resolution | Import resolution / linking |

### Key Insight: Registry is Link-Time, Not Runtime

The registry isn't a runtime concept - it's a **link-time** concept. For single-worker Python usage, there's nothing to link. The registry only matters when the CLI needs to link multiple `.worker` and `.py` files together.

- `load_worker()` = compile one file, get callable
- CLI + registry = link multiple files, resolve cross-references
- `WorkerToolset` = import stub for cross-module calls

### Worker Calling Worker: Mixed Static/Dynamic

When Worker A calls Worker B at runtime:

| Phase | What happens | Compiler analogy |
|-------|--------------|------------------|
| Load | Parse .worker file | Compilation |
| Link | Resolve toolsets, wrap workers in WorkerToolset | Linking, import resolution |
| Runtime | LLM decides to call tool | Interpreter dispatch |
| Call | WorkerToolset sets up context, invokes target | Thunk/trampoline execution |

This combines:
- **Static scoping**: What tools Worker A *can* call is fixed at definition time (like imports)
- **Dynamic dispatch**: *Which* tool to call is decided at runtime by the LLM (like vtable lookup)

The LLM acts as an **embedded interpreter** - the Worker is a compiled module with an interpreter inside that has access to the import table (toolsets) and decides at runtime what calls to make.

`WorkerToolset` is literally a **trampoline**: it intercepts the call, adjusts context (creates child frame, increments depth), and jumps to the real implementation.

## Migration

1. ~~**Create `WorkerToolset` adapter**~~ - DONE (`tasks/completed/214-worker-toolset-adapter.md`)
2. ~~**Remove Worker's AbstractToolset inheritance**~~ - DONE (Worker no longer inherits from AbstractToolset)
3. Define `Entry` protocol, have `Worker` implement it
4. Create `@entry` decorator for Python functions, with optional `toolsets=[...]`
   to declare explicit scope for `ctx.call(...)`
5. Add `load_worker()` for direct Worker loading
6. Rename `Invocable` → `Entry`, `InvocableRegistry` → `EntryRegistry`
7. Delete `ToolInvocable` class
