# Unified Entry Function Design

## Status
Brainstorm / Design exploration

## Two Planes of Execution

All orchestration code operates across two planes:

**Tool Plane** - Observable, instrumented execution:
- `ctx.call()` / toolsets / worker invocations
- Approval wrapping and policy hooks (per runtime `RunApprovalPolicy`, plus toolset pre-approval rules)
- Depth tracking and event callbacks
- Tool events emitted for observability

**Raw Python Plane** - Direct execution, no guardrails:
- File I/O, subprocess, network calls done directly in code
- No approvals, no tool events, no policy hooks
- Not observable by the framework

Direct tool instantiation (constructing tool classes and calling methods) is also raw-Python work; it bypasses the tool plane entirely and is outside this progression.

This distinction keeps the parity story honest: steps 1-3 have **identical tool plane behavior**, but raw Python in your entry function was never wrapped in any step. When we say "same environment," we mean the tool plane.

Approval behavior in the tool plane is controlled by runtime `RunApprovalPolicy` (mode: `prompt`, `approve_all`, `reject_all`). There is no per-call bypass; to skip prompts for a run, use `approve_all` (or `reject_all` to hard-deny), or drop to raw Python. Toolsets can include pre-approval rules via `set_toolset_approval_config`.

**Trust model**: Entry functions (step 2+) are trusted code from the start - they can run arbitrary Python. The tool plane wrapping on `ctx.call()` isn't about gatekeeping the entry function's decisions; it serves two purposes:

1. **Refactoring smoothness** - identical tool plane behavior means Worker → Entry is a pure refactor with no behavior change
2. **Observability** - visibility into what tool calls the trusted code triggers

This is different from workers (step 1) where the LLM makes decisions and approval gates those decisions. In entry functions, tool plane wrapping is about parity and visibility, not a trust boundary.

Code can always escape to raw Python. That's a feature, not a bug - but those operations are outside the framework's observability. If you need policy control over file access, use a filesystem toolset rather than `open()`.

## The Progression Path

We want a smooth progression for orchestration logic:

| Step | Plane | Who decides | Code trusted? | Notes |
|------|-------|-------------|---------------|-------|
| 1. Worker | Tool | LLM | N/A | Approval gates LLM decisions |
| 2. Entry | Tool | Code | Yes | Trusted code, observable tool calls |
| 3. Script | Tool | Code | Yes | Orthogonal: Python embedding without CLI |
| 4. Plain | Raw Python | Code | Yes | Leave observability, own visibility |

**Key insight**: Steps 1-3 all stay in the **tool plane**. This isn't primarily about trust - it's about **smooth refactoring** with identical observable behavior.

If Worker and Entry have different tool plane behavior (different wrapping, different approval behavior), then extracting orchestration logic from a Worker's LLM instructions into an Entry function **changes observable behavior**. That's refactoring friction.

The goal: **Worker → Entry should be a pure refactor**:
- Same tool plane behavior
- Same approval flow for `ctx.call()`
- Same events emitted
- Same depth tracking
- Only the decision-maker changes (LLM → code)

**Step 3 is orthogonal, not sequential.** The main progression is 1 → 2 → 4. Step 3 (script mode) is a deployment option you can take at any tool-plane step when you need Python embedding without CLI scaffolding:
- Integration into larger Python services
- Running as a daemon
- Test harnesses that want real tool plane behavior

Script mode still relies on registry linking to resolve named toolsets; a registry-free bootstrap is a future step.

You might stay at step 3 forever if Python embedding is your deployment target.

**Step 4 is leaving the tool plane.** You were already trusted (step 2+), but now you're also giving up framework-managed observability. You take explicit control - create the environment yourself, decide whether to set up event callbacks, pass dependencies explicitly. The tool plane still exists if you want it; you're just responsible for setting it up.

## The Core Insight

An entry function with access to multiple workers for orchestration is the same thing as an "orchestrator worker" with those workers in its toolsets - just without the LLM making decisions. The entry should be invoked as its own call (like a worker invocation), not as a literal tool call.

| Orchestrator Worker | Entry Function |
|---------------------|----------------|
| LLM decides which workers to call | Python code decides (trusted) |
| Approval gates LLM decisions | Same tool plane (parity + observability) |
| Workers available as toolsets | Same workers available via runtime |
| Full initialization (depth, events) | Same initialization |

The entry function is a **headless orchestrator** - same capabilities, same environment, but deterministic Python logic instead of LLM reasoning.

## Current Code Is Wrong

```python
# Current (Runtime.run_entry):
# "Entry functions are trusted code; tool calls run directly without approval wrappers"
```

The comment conflates two things: yes, entry functions are trusted code (they can run arbitrary Python). But that's orthogonal to whether tool calls go through the tool plane. Entry functions should stay in the tool plane for two reasons:

1. **Smooth refactoring** - Worker → Entry should have identical tool plane behavior
2. **Observability** - events, depth tracking, auditable tool calls

The trust model changed (code is trusted), but the tool plane should stay the same.

## Unified Environment Concept

The key architectural insight is separating **tool plane setup** from **execution method**.

**Tool Plane Setup** (same for steps 1-3):
- CallFrame + WorkerRuntime with resolved toolsets
- Approval wrapping applied per runtime policy (may be disabled)
- Depth tracking
- Event callbacks for observability
- Message history
- Toolset cleanup

**Execution Method** (differs per step):
- Worker: LLM agent loop
- Entry: Python code
- Script: Python code (via bootstrap API)
- Plain: Python code (tool plane optional, passed explicitly)

The environment builder should be **reusable** across all modes. Currently:
- `Worker._call_internal()` builds its own environment
- `Runtime.run_entry()` builds a different/lighter environment for EntryFunction

Proposed: One shared environment builder, with execution method as a parameter or determined by entry type. This ensures entry functions run in the same invocation environment as workers, with the same initialization, wrapping, and cleanup.

## Proposed Architecture Building Blocks

### 1. Shared Tool Plane Builder
Build a CallFrame + WorkerRuntime with resolved toolsets, prompt, messages, and approval wrapping. This builder is used by workers, entry functions, and scripts alike - anything that stays in the tool plane.

### 2. Entry-as-Invocation Pipeline
Run entry functions through the same invocation path as workers: create a CallFrame for the entry (depth 0 at top level), wrap toolsets for approval, set prompt/messages, then execute the entry. When invoked from another runtime, the entry uses a child CallFrame like any other invocation. This makes entry behavior match the worker "agent runtime" (where tool calls actually happen) without pretending the entry is a tool.

### 3. Script Bootstrap API
Provide a library-level helper that builds the environment and runs the entry directly in Python, using the same toolset resolution and cleanup. For now, script mode requires an EntryRegistry (or a pre-resolved Entry) so named toolsets can be resolved:

```python
from llm_do.runtime.registry import build_entry_registry

runtime = Runtime(cli_model="...", run_approval_policy=RunApprovalPolicy(mode="prompt"))
registry = build_entry_registry(worker_files=[...], python_files=[...])
entry = registry.get("main")
result = await runtime.run_entry(entry, {"input": "hello"})
```

A registry-free bootstrap (passing only ToolsetSpec objects and skipping name resolution) is a future step once we have more embedding examples.

### 4. Plain Function Endpoint (Leaving the Tool Plane)
The tool plane still exists if you want it - but you're responsible for setting it up. This is the explicit decision to leave framework-managed observability:

```python
# Step 4: Plain function - outside tool plane by default
async def my_logic(tool_router: ToolRouter) -> str:
    # No approval wrapping, no tool events unless you set them up
    result = await tool_router.call("analyzer", input)
    return result

# Caller decides whether to set up tool plane
router = ToolRouter(workers={...}, toolsets={...})  # unwrapped - raw Python plane
result = await my_logic(router)
```

Prefer passing a small ToolRouter or Services object rather than the full runtime so the function is not tied to PydanticAI types. The caller takes ownership of whether to wrap for approval - you're in the raw Python plane unless you explicitly opt back in.
For now, passing `WorkerRuntime` directly is acceptable; a minimal ToolRouter can be introduced later once we have more examples and know what is essential.

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

The change is to keep entry functions in the **same tool plane** as workers:

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
# - Uses same tool plane setup as Worker
# - Same approval policy for ctx.call()
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

1. **Tool plane builder** - Extract from `Worker._call_internal()`, make reusable
2. **Runtime.run_entry()** - Use shared builder for both Worker and EntryFunction
3. **Entry-as-invocation path** - Entry runs in its own CallFrame (depth 0 at top level), while workers execute in a child CallFrame (depth 1); tool calls do not change depth
4. **Approval wrapping** - Apply to entry function `ctx.call()` (currently bypassed)
5. **Remove "trusted code" bypass** - Entry functions stay in tool plane like workers

## Worker Access Model

Entry functions (steps 1-3) stay in the tool plane: **declare toolsets, call through standard machinery**. The entry itself is an invocation (like a worker), not an inline tool call. All `ctx.call()` invocations go through the tool plane and emit tool events; approvals apply per runtime policy.

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
- Name collisions between workers and toolsets are errors; detect and raise at registry build time.

## Open Questions

1. **Registry-free script mode**: Do we want a ToolsetCatalog (or similar) so named toolsets can be resolved without building a full EntryRegistry?

## Resolved

1. **Per-call toolset instantiation**: Fixed in `tasks/completed/per-call-toolset-instances.md`. Workers now store `toolset_specs` and instantiate per-call in `Worker._call_internal()` with cleanup in finally block.
2. **Attachment paths**: Resolve relative to a single runtime project root shared across workers (CLI uses manifest dir; scripts pass explicitly, e.g., `Path.cwd()` if desired). Per-worker attachment base paths are removed.
3. **Toolset build context**: `ToolsetBuildContext` no longer carries `worker_path`/`worker_dir`; toolset factories receive only explicit inputs.
4. **Step 4 interface**: Allow `WorkerRuntime` as the dependency surface for now; a smaller ToolRouter is deferred until more examples exist.
5. **Script bootstrap**: Require an EntryRegistry (or pre-resolved Entry) to resolve named toolsets; registry-free mode is deferred.

## Operational Notes

- Tool plane behavior (approval policy, events, depth) must be identical across steps 1-3
- Step 4 leaves the tool plane by default; if you opt back in, approvals are still runtime-wide
- Script mode currently requires registry linking for named toolsets; registry-free bootstrap is deferred
- Toolset cleanup needs to be owned by the environment builder so script mode can dispose resources without CLI scaffolding
- Message history, attachments, and tool events should be available to entry functions (same as workers)
- Attachment paths resolve relative to the runtime project root, not worker-specific paths
- Raw Python code in any step is outside the tool plane - if you need policy control, use a toolset
- Depth is CallFrame stack depth (worker invocation depth). Top-level entry runs at depth 0; top-level worker runs at depth 1; tool calls do not change depth.
- Event attribution should follow invocation ownership: tool events emitted during entry functions should carry the entry name as `worker`, not a generic `code_entry`. Child workers should emit events under their own names when they run.

## Benefits

1. **Smooth refactoring**: Worker → Entry are pure refactors with identical tool plane behavior
2. **Honest parity claim**: Tool plane has parity; raw Python is explicitly outside scope
3. **Clear trust model**: Entry functions are trusted code; tool plane is for parity and observability, not gatekeeping
4. **Clearer mental model**: Entry function is a headless orchestrator in the same tool plane as worker
5. **Consistent interface**: `ctx.call()` works the same in entry functions and workers
6. **Opt-in model preserved**: Entry functions declare toolsets explicitly, same as workers
7. **Flexible deployment**: Step 3 (script) is orthogonal - use it when Python embedding is needed
8. **Easier testing**: Same tool plane means same test setup for workers and entry functions

## Migration Path

1. Extract tool plane builder from `Worker._call_internal()` into shared function
2. Update `Runtime.run_entry()` to use shared builder for EntryFunction
3. Route entry execution through the child CallFrame invocation path (same as workers)
4. Remove "trusted code" approval bypass - entry `ctx.call()` stays in tool plane
5. Verify entry functions get same tool plane behavior (toolsets, depth, events, cleanup)

## Related Notes

- `docs/notes/execution-mode-scripting-simplification.md` - Similar goals for Python embedding
- `docs/notes/worker-design-rationale.md` - Core worker design principles
- `tasks/completed/per-call-toolset-instances.md` - Toolset isolation (now fixed)
