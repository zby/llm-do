# Unified Entry Function Design

## Status
Brainstorm / Design exploration

## The Progression Path

We want a smooth progression for orchestration logic:

| Step | Environment | Who decides | Refactor from previous |
|------|-------------|-------------|------------------------|
| 1. Worker | Full (wrapped, implicit) | LLM | - |
| 2. Entry | Full (wrapped, implicit) | Code | Pure refactor (extract logic) |
| 3. Script | Full (wrapped, implicit) | Code | Pure refactor (remove CLI) |
| 4. Plain | Full (unwrapped, explicit) | Code | Conscious change (take ownership) |

**Key insight**: Steps 1-3 all use the **same wrapped environment**. This isn't primarily about trust - it's about **smooth refactoring**.

If Worker and Entry have different environments (different wrapping, different approval behavior), then extracting orchestration logic from a Worker's LLM instructions into an Entry function **changes behavior**. That's refactoring friction.

The goal: **Worker → Entry should be a pure refactor**:
- Same environment
- Same tool behavior
- Same events
- Same approval flow
- Only the decision-maker changes (LLM → code)

Only at step 4 (plain function) do you take explicit control of the environment - you create it yourself, decide whether to wrap for approval, and pass it in. The environment still exists; it's just your responsibility now.

## The Core Insight

An entry function with access to multiple workers for orchestration is the same thing as an "orchestrator worker" with those workers in its toolsets - just without the LLM making decisions.

| Orchestrator Worker | Entry Function |
|---------------------|----------------|
| LLM decides which workers to call | Python code decides which workers to call |
| Workers available as toolsets | Same workers available via runtime |
| Full initialization (approval, depth, events) | Same initialization |

The entry function is a **headless orchestrator** - same capabilities, same environment, but deterministic Python logic instead of LLM reasoning.

## Current Code Is Wrong

```python
# Current (Runtime.run_entry):
# "Entry functions are trusted code; tool calls run directly without approval wrappers"
```

Should be: Entry functions use the same approval-wrapped toolsets as workers. Keeping the environment identical ensures the Worker → Entry refactor is frictionless.

## Unified Environment Concept

The key architectural insight is separating **invocation environment** from **execution method**.

**Invocation Environment** (same for steps 1-3):
- CallFrame + WorkerRuntime with resolved toolsets
- Approval wrapping applied
- Depth tracking
- Event callbacks
- Message history
- Toolset cleanup

**Execution Method** (differs per step):
- Worker: LLM agent loop
- Entry: Python code
- Script: Python code (via bootstrap API)
- Plain: Python code (environment passed explicitly)

The environment builder should be **reusable** across all modes. Currently:
- `Worker._call_internal()` builds its own environment
- `Runtime.run_entry()` builds a different/lighter environment for EntryFunction

Proposed: One shared environment builder, with execution method as a parameter or determined by entry type. This ensures entry functions truly run "as if" they were tools in a worker, with the same initialization, wrapping, and cleanup.

## Proposed Architecture Building Blocks

### 1. Shared Environment Builder
Build a CallFrame + WorkerRuntime with resolved toolsets, prompt, messages, and approval wrapping. This builder is used by workers, entry functions, and scripts alike.

### 2. Entry-as-Tool Adapter
Wrap a code entry as a tool so it can be invoked via `ctx.call()` with the same validation and event semantics as tool calls. This enables the "entry behaves like a tool call" step.

### 3. Script Bootstrap API
Provide a library-level helper that builds the environment and runs the entry directly in Python, using the same toolset resolution and cleanup:

```python
# Plain Python - same environment as CLI
runtime = Runtime(cli_model="...", approval_policy=...)
workers = {"main": Worker(...), "helper": Worker(...)}
result = await runtime.run(workers["main"], {"prompt": "hello"})
```

### 4. Plain Function Endpoint
The environment still exists - tool/worker calls still need it. The difference is that you create and pass it explicitly:

```python
# Step 4: Plain function with explicit dependencies
async def my_logic(tool_router: ToolRouter) -> str:
    # Environment exists, but you created it and passed it in
    result = await tool_router.call("analyzer", input)
    return result

# Caller creates the environment explicitly
router = ToolRouter(workers={...}, toolsets={...})  # unwrapped
result = await my_logic(router)
```

Prefer passing a small ToolRouter or Services object rather than the full runtime so the function is not tied to PydanticAI types. The caller takes ownership of environment creation (including the decision to wrap or not wrap for approval).

## Current Architecture Analysis

### The Split

| Component | What it holds | What it does |
|-----------|---------------|--------------|
| **EntryRegistry** | `dict[str, Entry]` (workers + entry funcs) | Symbol table for lookup; built from .worker/.py files |
| **Runtime** | RuntimeConfig, UsageCollector, MessageAccumulator | Execution environment; runs entries; no knowledge of registry |
| **Entry** (Worker/EntryFunction) | name, toolsets, schema_in | Passed to `Runtime.run_entry()` |
| **WorkerRuntime** | Runtime + CallFrame | Per-call context; can call tools via `active_toolsets` |
| **CallFrame** | depth, model, active_toolsets, prompt, messages | Per-call state |

### Key Observation

Entry functions declare toolsets and call through standard machinery - same as workers. This is consistent with the opt-in tool model (see `worker-design-rationale.md`). The current design is correct here.

```python
@entry(toolsets=["analyzer", "writer", "filesystem"])
async def orchestrate(args, ctx):
    # Can only call declared toolsets - same as a worker
    result = await ctx.call("analyzer", {"prompt": "..."})
    await ctx.call("writer", {"prompt": result})
```

The entry function declares what it needs upfront. This is explicit and auditable - you can read the declaration and know exactly what it can do.

## API Changes Needed

The main change is **not** to the entry function signature - that stays the same (declares toolsets, receives WorkerRuntime, calls tools).

The change is to make entry functions use the **same wrapped environment** as workers:

### Current (Wrong)

```python
# Runtime.run_entry() for EntryFunction:
# - Builds lighter environment
# - Bypasses approval wrapping
# - Different initialization path than Worker
```

### Proposed (Correct)

```python
# Runtime.run_entry() for EntryFunction:
# - Uses same environment builder as Worker
# - Same approval wrapping
# - Same initialization (toolsets, depth, events, cleanup)
# - Only difference: execution method (code vs LLM)
```

### Entry Function Signature (Unchanged)

```python
@entry(toolsets=["analyzer", "writer"])
async def orchestrate(args: WorkerArgs, ctx: WorkerRuntime) -> str:
    # Same signature, same ctx.call() pattern
    result = await ctx.call("analyzer", {"prompt": args.prompt_spec().text})
    return await ctx.call("writer", {"prompt": result})
```

### What Changes

1. **Environment builder** - Extract from `Worker._call_internal()`, make reusable
2. **Runtime.run_entry()** - Use shared builder for both Worker and EntryFunction
3. **Approval wrapping** - Apply to entry functions (currently bypassed)
4. **Remove "trusted code" bypass** - Entry functions go through same path

## Worker Access Model

Entry functions (steps 1-3) use the same model as workers: **declare toolsets, call through standard machinery**.

```python
@entry(toolsets=["analyzer", "writer", "filesystem"])
async def entry(args, ctx):
    # Workers are toolsets - call by name
    await ctx.call("analyzer", {"prompt": "..."})
    await ctx.call("writer", {"prompt": "..."})
    # Regular tools work the same way
    await ctx.call("filesystem", {"action": "read", "path": "..."})
```

This is the opt-in model from `worker-design-rationale.md`:
- Explicit declaration of what's available
- Auditable - read the declaration to know capabilities
- Same pattern for workers and entry functions

## Open Questions

1. **Base paths**: How should toolset resolution handle base paths when running outside llm-do (cwd vs worker file path vs explicit project root)?

2. **ToolRouter interface**: What is the minimal interface needed so plain functions (step 4) can stay decoupled from PydanticAI types?

3. **Script bootstrap API**: What's the minimal API for step 3 (running entry from Python without CLI)?

## Resolved

1. **Per-call toolset instantiation**: Fixed in `tasks/completed/per-call-toolset-instances.md`. Workers now store `toolset_specs` and instantiate per-call in `Worker._call_internal()` with cleanup in finally block.

## Operational Notes

- Approval wrapping should remain consistent across steps 1-3; only step 4 removes it
- Toolset cleanup needs to be owned by the environment builder so script mode can dispose resources without CLI scaffolding
- Message history, attachments, and tool events should be available to entry functions (same as workers)

## Benefits

1. **Smooth refactoring**: Worker → Entry → Script are pure refactors with no behavior change
2. **Clearer mental model**: Entry function is a headless orchestrator with same environment as worker
3. **Consistent interface**: `ctx.call()` works the same in entry functions and workers
4. **Opt-in model preserved**: Entry functions declare toolsets explicitly, same as workers
5. **Easier testing**: Same environment means same test setup for workers and entry functions

## Migration Path

1. Extract environment builder from `Worker._call_internal()` into shared function
2. Update `Runtime.run_entry()` to use shared builder for EntryFunction
3. Remove "trusted code" approval bypass for entry functions
4. Verify entry functions get same initialization (toolsets, depth, events, cleanup)

## Related Notes

- `docs/notes/execution-mode-scripting-simplification.md` - Similar goals for Python embedding
- `docs/notes/worker-design-rationale.md` - Core worker design principles
- `tasks/completed/per-call-toolset-instances.md` - Toolset isolation (now fixed)
