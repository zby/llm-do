# Remove Worker Class and Adopt Experiment Runtime

## Status
completed

## Prerequisites
- [x] none (design locked)

## Goal
Remove the `Worker` class from llm-do and make the experiment runtime (`deps`-as-runtime from `experiments/pydanticai-runtime-deps/`) the primary execution surface, with proper lifecycle management via `CallScope` and a unified `Entry` abstraction.

## Context

### Relevant files/symbols
- `llm_do/runtime/worker.py` — current `Worker` class to be removed
- `llm_do/runtime/deps.py` — `WorkerRuntime` facade
- `experiments/pydanticai-runtime-deps/runtime.py` — `AgentRuntime` (experiment runtime)
- `experiments/pydanticai-runtime-deps/runtime-delta-list.md` — gap analysis
- `llm_do/runtime/contracts.py` — existing entry contracts

### Related tasks/notes/docs
- `docs/notes/experiment-runtime-without-worker.md` — original analysis
- `experiments/pydanticai-runtime-deps/README.md` — experiment architecture

### Key findings (inlined from note)
- `WorkerRuntime` alone does not cover lifecycle, toolset cleanup, or prompt/agent orchestration; those behaviors live in `Worker` today.
- Removing `Worker` means relocating its responsibilities into:
  - a call-scope/lifecycle abstraction (build toolsets per call, run agent, cleanup),
  - an `Entry` abstraction (agents + Python callables),
  - a runtime state object for usage + message log aggregation.
- The experiment runtime lacks run-scoped sinks, call-scope boundaries, entry resolution, and model compatibility logic.
- `WorkerRuntime` can remain a facade if it wraps shared run-state (`Runtime`) plus per-call state (`CallFrame`).

### Background: What Worker Does Today
The `Worker` class currently handles:
1. **Lifecycle management** — build toolsets per call, run agent, cleanup
2. **Prompt/agent orchestration** — constructing prompts, running the agent
3. **Toolset cleanup** — ensuring `cleanup()` hooks are called after runs

`WorkerRuntime` alone does not cover these; it only provides the delegation surface (`call_agent`, `call_tool`) and shared state access.

### Design Decision: Toolset Instantiation in CallScope
If `Worker` is removed, toolset instantiation should live in `CallScope` (not the deps/runtime object):

- **Lifecycle alignment:** CallScope is responsible for per-call lifecycle and cleanup, so it should ensure toolsets are torn down after the run.
- **Testability:** CallScope-bound toolset creation makes it easier to test "per call" behavior without relying on global runtime state.
- **Runtime as facade:** If the runtime stays a facade over shared state, keeping construction in CallScope preserves the separation between "shared run state" and "per-call resources".

This implies keeping a small helper (e.g., `ToolsetResolver`) owned by runtime (or passed into CallScope) so CallScope can ask for toolsets when it starts, but CallScope should own instantiation and cleanup ordering.

### Current Bug: Experiment Leaks Toolsets
The experiment's `AgentRuntime.call_agent()` builds toolsets but never cleans them up:

```python
# experiments/pydanticai-runtime-deps/runtime.py:107-128
async def call_agent(self, name, prompt, *, ctx):
    toolsets = child.toolsets_for(agent, agent_name=name)
    result = await agent.run(..., toolsets=toolsets)
    return result.output  # BUG: toolsets never cleaned up!
```

**The fix is NOT to add try/finally here.** The proper solution is to use `CallScope` for lifecycle management, which is how the main trunk handles this (see `Worker.call()` at `worker.py:475-481`):

```python
# Correct approach: use CallScope for lifecycle
async def call_agent(self, name, prompt, *, ctx):
    agent = self.agents.get(name)
    entry = AgentEntry(agent, name)  # Entry wrapper for PydanticAI agent
    scope = entry.start(self.runtime)
    try:
        return await scope.run_turn(prompt)
    finally:
        await scope.close()

# Or with async context manager:
async def call_agent(self, name, prompt, *, ctx):
    entry = AgentEntry(agent, name)
    async with entry.start(self.runtime) as scope:
        return await scope.run_turn(prompt)
```

This is why "Implement `AgentEntry` wrapper" and "Make experiment use existing `CallScope`" are prerequisites for fixing this bug properly.

### What the Experiment Runtime Lacks (from delta list)
1. **Run-scoped state & sinks** — aggregated usage and message logs across nested calls
2. **CallScope-like boundary** — structured per-call lifecycle with toolset cleanup
3. **Tool invocation from code** — `call_tool(name, args, ctx)` API for harness layer
4. **Entry abstraction** — unified interface for PydanticAI agents and `@entry` Python functions
5. **Model selection + compatibility** — respect `compatible_models` from worker frontmatter
6. **Approval workflow integration** — UI approval queue integration
7. **Runtime config surface** — clean config structure (max_depth, approval mode, etc.)
8. **Loader convergence** — shared parsing vs runtime-specific entry construction

### How to verify
- All existing tests pass after Worker removal
- Experiment runtime can execute `.worker` files and `@entry` functions
- Toolset cleanup is invoked on both success and error paths
- Usage aggregation works across nested agent calls

## Decision Record
- **Decision:** Toolset instantiation in CallScope, not runtime
- **Inputs:** Analysis of Worker responsibilities, testability concerns, lifecycle alignment
- **Options:** (1) Keep toolsets in runtime, (2) Move to CallScope, (3) Hybrid approach
- **Outcome:** Option 2 — CallScope owns toolset lifecycle
- **Follow-ups:** Design Entry interface, implement CallScope
- **Decision:** Adopt main trunk spawn semantics (Runtime + CallFrame + CallRuntime)
- **Inputs:** Need for per-call metadata (model, invocation_name), lifecycle alignment, clearer separation of shared vs per-call state
- **Options:** (1) Keep experiment spawn() depth-only, (2) Adopt main trunk spawn_child semantics, (3) Hybrid spawn with optional params
- **Outcome:** Option 2 — Runtime.spawn_call_runtime factory + CallFrame depth increments
- **Follow-ups:** Rename WorkerRuntime -> CallRuntime; add Runtime.spawn_call_runtime factory
- **Decision:** Tool invocation only via CallScope; Entry.run_turn receives CallScope
- **Inputs:** Lifecycle ownership of toolsets, explicit scope ownership, avoid hidden globals
- **Options:** (1) Disallow direct tool calls in Entry, (2) Pass CallScope to Entry.run_turn, (3) Contextvar for active scope
- **Outcome:** Option 2 — Entry.run_turn(scope, input_data); CallScope is sole tool surface
- **Follow-ups:** Update Entry protocol + CallScope.run_turn; move call_tool to CallScope

## Tasks
- [x] Resolve where `call_tool` belongs → CallScope (owns toolset instances)
- [x] Resolve CallScope → use existing `CallScope` from `llm_do/runtime/call.py:85-109`
- [x] Reconcile spawn semantics → adopt `Runtime` + `CallFrame` + `CallRuntime` with `Runtime.spawn_call_runtime` factory
- [x] Confirm Entry protocol signature in code (current: `run_turn(runtime, input_data)` in `llm_do/runtime/contracts.py`)
- [x] Update Entry protocol signature and implementations to `run_turn(scope, input_data)`
- [x] Implement `AgentEntry` wrapper that conforms to `Entry` protocol for PydanticAI agents
- [x] Make experiment runtime adopt `CallScope` lifecycle (entry + toolsets + cleanup via async context manager)
- [x] Implement `CallScope.call_tool` and remove tool calls from runtime facade
- [x] Implement `RunState` for usage + message log aggregation
- [x] Integrate model compatibility checks in experiment loader
- [x] Wire approval callback to UI queue controller
- [x] Create `RuntimeConfig` dataclass for experiment
- [x] Migrate unit tests (runtime + entry abstractions)
- [x] Migrate integration tests (worker files + approval flow)
- [x] Remove Worker class
- [x] Rename WorkerRuntime -> CallRuntime (and protocol types)

### Ordering / Dependencies
- Update Entry protocol → Implement `AgentEntry` → Adopt CallScope in experiment runtime
- Implement `CallScope.call_tool` → Remove tool calls from runtime facade

### Decision: Rename Timing
Prefer renaming **late** (after new architecture is in place) to minimize churn while behavior is still shifting. Revisit only if the type names become a blocker during implementation.

## Current State
Completed implementation. Worker has been removed in favor of AgentEntry + CallScope, CallRuntime now backs deps, CallScope owns tool invocation, and tests/examples have been updated to use scope.call_tool.

## Notes
- `WorkerRuntime` can remain as a facade wrapping shared run-state (`Runtime`) plus per-call state (`CallFrame`)
- The experiment already has `ToolsetResolver` — this can be reused by CallScope
- Attachments are already converged with main trunk (uses `Attachment` class + `render_prompt()`)

### Resolved: Tool Plane Location
`call_tool()` belongs in `CallScope`, not on the deps object. Reasoning: toolsets are instantiated per-call in CallScope, so only CallScope can invoke tools. The deps object (`AgentRuntime`) doesn't own toolset instances.

```python
# CallScope owns toolsets and exposes call_tool
async with CallScope(runtime, agent_name) as scope:
    result = await scope.call_tool("shell", {"command": "ls"})
    result = await scope.run_agent(prompt)
```

### Resolved: Spawn semantics (CallRuntime)

**AgentRuntime.spawn() (experiment):**
```python
def spawn(self) -> "AgentRuntime":
    if self.depth >= self.max_depth:
        raise RuntimeError(f"max_depth exceeded")
    return replace(self, depth=self.depth + 1)
```

**WorkerRuntime.spawn_child() (main trunk):**
```python
def spawn_child(
    self,
    active_toolsets: Sequence[AbstractToolset[Any]],
    *,
    model: ModelType,
    invocation_name: str,
) -> "WorkerRuntime":
    return WorkerRuntime(
        runtime=self.runtime,  # shared state preserved
        frame=self.frame.fork(active_toolsets, model=model, invocation_name=invocation_name),
    )
```

**Key differences:**
| Aspect | Experiment | Main Trunk |
|--------|------------|------------|
| Toolsets | Resolved later in `call_agent` | Passed at spawn time |
| Model tracking | None | `CallFrame.config.model` |
| Invocation name | None | For tracing/debugging |
| State separation | Flat dataclass | `Runtime` (shared) + `CallFrame` (per-call) |

**Recommendation:** Make the experiment adopt main trunk's `Runtime` + `CallFrame` + `CallRuntime` architecture with a `Runtime.spawn_call_runtime` factory rather than reconciling two different approaches. This provides:
- Clear separation of shared vs per-call state
- Model and invocation tracking for debugging
- Consistent `spawn_child()` signature

### Resolved: CallScope Already Exists (will own tool calls)
The `CallScope` class is already defined in `llm_do/runtime/call.py:85-109`:

### Target Design: CallScope delegates via scope
This snippet shows the **intended** `Entry.run_turn(scope, input_data)` signature. The current code may differ; align it during implementation.

```python
@dataclass(slots=True)
class CallScope:
    """Lifecycle wrapper for an entry call scope (runtime + toolsets)."""

    entry: "Entry"
    runtime: WorkerRuntimeProtocol
    toolsets: Sequence["AbstractToolset[Any]"]
    _closed: bool = False

    async def run_turn(self, input_data: Any) -> Any:
        if self._closed:
            raise RuntimeError("CallScope is closed")
        return await self.entry.run_turn(self, input_data)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await cleanup_toolsets(self.toolsets)

    async def __aenter__(self) -> "CallScope": ...
    async def __aexit__(self, ...): await self.close()
```

CallScope responsibilities (current behavior may need signature alignment):
- Holds `entry`, `runtime`, and instantiated `toolsets`
- Delegates `run_turn()` to the entry (ensure scope is passed per target signature)
- Handles toolset cleanup on `close()` or context exit
- Supports async context manager (`async with`)

**Work needed:** Update CallScope.run_turn to pass itself into `Entry.run_turn(scope, input_data)` and add `CallScope.call_tool` as the sole tool invocation surface.

### Resolved: Entry Interface Already Exists (signature update required)
The `Entry` protocol is already defined in `llm_do/runtime/contracts.py:52-93`:

This snippet shows the **intended** signature. Confirm the current protocol in code and update if needed.

```python
class Entry(Protocol):
    @property
    def name(self) -> str: ...

    def start(
        self,
        runtime: "Runtime",
        *,
        message_history: list[Any] | None = None,
    ) -> "CallScope": ...

    async def run_turn(
        self,
        scope: CallScope,
        input_data: Any,
    ) -> Any: ...

    @property
    def toolset_specs(self) -> list[ToolsetSpec]: ...

    @property
    def schema_in(self) -> type["WorkerArgs"] | None: ...
```

The Entry/CallScope split already exists:
- Entry creates CallScope via `start()`
- CallScope handles per-turn execution and tool invocation
- `toolset_specs` defines what toolsets the entry needs
- `schema_in` defines optional structured input

**Work needed:** Update the Entry protocol and implementations to accept CallScope in `run_turn`, then make the experiment's `AgentRuntime` compatible with the updated protocol.
