# Remove Worker Class — Toolset-First Design

## Status
ready for implementation

## Goal
Remove the `Worker` class and the `Entry` protocol. Replace with a simpler model where:
- **Toolsets contain functions** (including a `main` function as entry point)
- **CallScope/CallFrame can invoke any function** in its toolsets
- **Agents are just toolsets** where `main` wraps `agent.run()`

## Design Summary

### Before (Current)
```
Entry protocol (EntryFunction, AgentEntry)
    ↓
CallScope (wraps entry + runtime + toolsets)
    ↓
Entry.run_turn(scope, input) → executes entry logic
    ↓
scope.call_tool() → invokes tools
```

### After (Proposed)
```
Toolsets (one function named "main" is the entry point)
    ↓
CallScope (wraps runtime + toolsets, no Entry)
    ↓
scope.call_tool("main", input) → executes entry
    ↓
main() can call_agent() → agent picks tools from toolset
```

## Key Simplifications

1. **No Entry protocol** — Delete `Entry`, `EntryFunction`, `AgentEntry` abstractions
2. **Entry toolset has only `main`** — No other tools; `main` orchestrates by calling agents
3. **Primary invocation via call_tool** — Entry is `scope.call_tool("main", args)`
4. **Agents as toolsets** — A PydanticAI agent becomes a toolset with `main` that wraps `agent.run()`
5. **`call_agent` for orchestration** — Entry's `main` calls agents; agents have their own tools

## Toolset Contract

A toolset that serves as an entry point must satisfy:

1. **Has only a `main` function** — Entry toolsets contain exactly one tool: `main`
2. **Builder returns ToolsetSpec** — Loaders return `ToolsetSpec` (as today), not instantiated toolsets
3. **Entry input mapping is explicit** — `EntrySpec.schema_in` (a `WorkerArgs` subclass) controls CLI normalization; otherwise `main` must accept `input` (and optional `attachments`) to match the default mapping
4. **Approval wrapping unchanged** — CallScope instantiates toolsets from specs and wraps with approval (existing behavior)

Note: Agents have their own toolsets with multiple tools. Entry toolsets are simple orchestrators.

### ToolsetSpec (unchanged)

The loader/builder returns `ToolsetSpec`, which is instantiated by CallScope:

```python
@dataclass
class ToolsetSpec:
    """Specification for a toolset to be instantiated."""
    factory: Callable[[ToolsetBuildContext], AbstractToolset]
    approval_config: dict[str, Any] | None = None
    # ... other metadata
```

### Entry Metadata

Entry-level metadata moves to a new structure that wraps the ToolsetSpec:

```python
@dataclass
class EntrySpec:
    """Specification for an entry point (root invocation)."""
    toolset_spec: ToolsetSpec          # The entry toolset (has only `main`)
    name: str                          # Entry name for logging/tracing
    description: str | None = None
    schema_in: type[WorkerArgs] | None = None  # Optional input schema for CLI normalization
```

Note: No `model` field - the entry's `main` calls agents, each with their own model.
`schema_in` (if provided) is used by `Runtime.run_entry()` to normalize CLI input into a
dict passed to `call_tool("main", ...)`; otherwise the entry `main` must accept `input`
(and optional `attachments`) to match the default input mapping.
The loader produces `EntrySpec` for `.worker` files. `Runtime.run_entry()` accepts `EntrySpec`.

## Ambiguity Resolutions (v3.2)

These clarifications close the remaining gaps that still allowed divergent implementations.

1. **`@entry` is removed, not reimplemented.** All Python entry code must be expressed as a toolset factory that defines exactly one tool named `main`.
2. **Entry input normalization stays explicit and CLI-compatible.** `Runtime.run_entry()` always calls `normalize_input(schema_in, input_data)` (where `schema_in` is `WorkerArgs` or `None`) and passes a dict to `call_tool("main", ...)`. If no schema is provided, the default mapping uses `input` + optional `attachments`; entry `main` must accept those names.
3. **Entry toolset enforcement is strict.** `Runtime.create_scope()` must assert the entry toolset exposes **exactly one tool named `main`** (no extras). Fail fast with a clear error.
4. **`call_agent` accepts `AgentSpec | str`, name resolution is runtime-owned.** `CallRuntime` keeps a registry of `AgentSpec` instances so entry tools can call `.worker`-defined agents by name without importing them.
5. **Agent toolsets are isolated per call.** `call_agent` instantiates the agent’s toolset specs and cleans them up via a `CallScope` (or equivalent async context). Do not reuse the entry toolset’s instances.
6. **`.worker` files map to `AgentSpec` first, then `EntrySpec` only if `entry: true`.** EntrySpec has no model; the model lives on the `AgentSpec`.
7. **Conversation history is bridged across entry → agent.** If the entry call has message history, the first `call_agent` must pass it into the agent run and update the parent frame’s messages afterward (preserves chat mode).
8. **Python entry selection is explicit and type-based.** Loaders collect `EntrySpec` instances from modules; there must be exactly one across Python files and no `.worker` entry conflict.
9. **AgentSpec is config, not a live Agent.** It stores model/instructions/toolset specs/etc; `call_agent` builds a fresh PydanticAI `Agent` per call with instantiated toolsets + builtin tools. Model compatibility is resolved when constructing the `AgentSpec`.

## Design Details

### Entry Toolset (only `main`)
```python
from pydantic_ai.toolsets import FunctionToolset

def build_my_entry(ctx):
    """Entry toolset has ONLY a main function."""
    toolset = FunctionToolset()

    @toolset.tool
    async def main(input: str, attachments: list[str] | None = None, *, ctx) -> str:
        """Entry point. Orchestrates by calling agents."""
        # Pure computation
        if "simple" in input:
            return f"Processed: {input}"

        # Or orchestrate multiple agents
        analysis = await ctx.deps.call_agent(analyzer_agent_spec, input)
        result = await ctx.deps.call_agent(writer_agent_spec, analysis)
        return result

    return toolset
```

Entry toolsets contain **only** `main`. Tools belong to agents, not the entry.

### AgentSpec (replaces Worker as a config holder)
```python
@dataclass
class AgentSpec:
    name: str
    instructions: str
    model: str | Model
    toolset_specs: list[ToolsetSpec]
    toolset_context: ToolsetBuildContext | None = None
    description: str | None = None
    schema_in: type[WorkerArgs] | None = None
    schema_out: type[BaseModel] | None = None
    model_settings: ModelSettings | None = None
    builtin_tools: list[Any] = field(default_factory=list)
```

`AgentSpec` is configuration only; `call_agent` constructs a fresh PydanticAI `Agent`
per call with instantiated toolsets and builtin tools.

### Agent as Toolset
```python
def agent_as_toolset(spec: AgentSpec) -> ToolsetSpec:
    """Expose an AgentSpec as a ToolsetSpec with a 'main' entry tool."""

    def factory(ctx: ToolsetBuildContext) -> AbstractToolset:
        toolset = FunctionToolset()

        @toolset.tool
        async def main(input_data: Any, *, ctx) -> str:
            """Run the agent with the given input."""
            # Use call_agent to ensure depth tracking
            return await ctx.deps.call_agent(spec, input_data)

        return toolset

    return ToolsetSpec(factory=factory)
```

The `main` function delegates to `call_agent`, which handles:
- Depth increment (before agent.run)
- Usage/message aggregation
- Toolset lifecycle for the agent's own tools

### Calling Agents from Entry
The entry's `main` function orchestrates by calling agents via `call_agent`:

```python
@toolset.tool
async def main(input: str, attachments: list[str] | None = None, *, ctx) -> str:
    # Call agents by reference (AgentSpec) or by name
    result = await ctx.deps.call_agent(helper_agent_spec, input)
    return result
```

Each `call_agent` increments depth. The called agent has its own toolsets.

### Root Invocation
```python
# Create runtime
runtime = Runtime(max_depth=5)

# Load entry spec (from .worker file or code)
entry_spec = EntrySpec(
    toolset_spec=my_entry_toolset_spec,
    name="my_entry",
)

# Run entry - creates scope, calls main, cleans up
result = await runtime.run_entry(entry_spec, {"input": "Hello"})
```

Or manually with CallScope:
```python
scope = runtime.create_scope(entry_spec)
try:
    result = await scope.call_tool("main", {"input": "Hello"})
finally:
    await scope.close()
```

### Depth Tracking

**Depth increments only in `call_agent`**, not in `call_tool`. This means:

- `scope.call_tool("main", ...)` on a plain function toolset → **no depth increment**
- `scope.call_tool("main", ...)` on an agent-as-toolset → **depth increments** (because `main` calls `call_agent` internally)
- `ctx.deps.call_agent(agent_spec, input_data)` from any tool → **depth increments**

The agent-as-toolset wrapper's `main` function delegates to `call_agent`, so depth is tracked correctly without `call_tool` needing to know whether it's invoking an agent or a plain function.

```python
# call_agent is the depth boundary
async def call_agent(self, spec: AgentSpec | str, input_data: Any) -> str:
    if self.frame.config.depth >= self.config.max_depth:
        raise RuntimeError("max_depth exceeded")

    child_runtime = self.spawn_child(depth=self.frame.config.depth + 1, ...)
    # ... run agent with child_runtime as deps
```

Namespacing is handled by `call_agent` - agents are identified by `AgentSpec.name` and can be called by spec or by name:
```python
# Entry's main calls agents by spec
await ctx.deps.call_agent(helper_agent_spec, input_data)
```

## Decisions (Locked)

### Depth Increment: Only via call_agent
Depth increments only in `call_agent()`, not in `call_tool()`. Agent-as-toolset wrappers call `call_agent` internally, so they increment depth. Plain function toolsets do not. This keeps `call_tool` simple (no agent detection) while still enforcing recursion limits on LLM calls.

### Agent Invocation from Tools (CallAgent)
Tools can invoke agents via `ctx.deps.call_agent(...)`. This is a targeted API to
enable orchestration without enabling general tool-to-tool calls.

### Conversation State: Agents Handle Their Own
- Tools don't need conversation history
- The first agent call in a run should receive the entry message history and update the parent frame afterward
- Runtime message logs/usage remain diagnostic; they are not conversation state

## Implementation Plan (Clarified — resolves v3 ambiguities)

### Phase 0: Realign the branch
- [ ] Stop work on Entry/Worker refactors; the target state is **no Entry protocol, no Worker class**
- [ ] Revert or discard changes that evolve `worker.py`/`Entry` instead of removing them
- [ ] Keep only the pieces that align with the toolset-first design (e.g., `CallScope.call_tool` may be salvageable)

### Phase 1: Contracts & runtime entry API
- [ ] Add `EntrySpec` and `AgentSpec` dataclasses to `contracts.py`
- [ ] Remove `Entry` protocol and any `run_turn`/`start` semantics
- [ ] Add `Runtime.spawn_call_runtime(toolsets, model, invocation_name, depth)` factory in `shared.py`
- [ ] Add `Runtime.create_scope(entry_spec)` that:
  - Instantiates the entry toolset from `EntrySpec.toolset_spec`
  - Wraps approval config
  - Validates the entry toolset exposes **exactly** one tool named `main`
  - Spawns a `CallRuntime` with `invocation_name = entry_spec.name` and `model = NULL_MODEL`
  - Returns a `CallScope` bound to that runtime/toolset list
- [ ] Update `Runtime.run_entry(entry_spec, input_data)` to:
  - Normalize input via `normalize_input(schema_in, input_data)` (schema_in is `WorkerArgs` or `None`)
  - Emit `UserMessageEvent` + set `runtime.frame.prompt` for top-level calls
  - Convert normalized input to a dict (`WorkerArgs.model_dump()` or default `{input, attachments}`)
  - Call `scope.call_tool("main", normalized_dict)` and close the scope

### Phase 2: CallScope + tool invocation
- [ ] Remove Entry references from `CallScope`; it should be `{runtime, toolsets, close(), call_tool()}`
- [ ] Ensure `call_tool()` uses the scope’s active toolsets (post-approval wrapping)
- [ ] Keep tool arg validation identical to PydanticAI tool calls (entry normalization happens before call_tool)
- [ ] Remove or make private `WorkerRuntime.call` to prevent tool-to-tool calls

### Phase 3: Agent invocation path
- [ ] Implement `call_agent(spec_or_name: AgentSpec | str, input_data)` on `CallRuntime` (depth increments here)
- [ ] `call_agent` responsibilities:
  - Resolve `AgentSpec` by name when a string is provided
  - Spawn child runtime with `depth+1` and `invocation_name = spec.name`
  - Instantiate `spec.toolset_specs`, wrap approvals, and manage cleanup via `CallScope`
  - Normalize input via `normalize_input(spec.schema_in, input_data)` and render prompt/attachments
  - Build a fresh PydanticAI `Agent` from the spec (model/instructions/output_type)
  - Pass instantiated toolsets + builtin tools + model_settings into `agent.run(...)`
  - If parent depth == 0 and parent has message history, pass it into the agent run and update the parent frame afterward
  - Aggregate usage + message log into the shared runtime state
- [ ] Create `agent_as_toolset(spec: AgentSpec) -> ToolsetSpec` in `llm_do/toolsets/agent.py`

### Phase 4: Loader & registry migration
- [ ] Update `.worker` loader to build `AgentSpec` objects (model, instructions, schema_in/out, toolsets)
- [ ] Register `AgentSpec` instances in an agent registry for name lookup in `call_agent`
- [ ] If `entry: true`, wrap the AgentSpec with `agent_as_toolset()` and then `EntrySpec`
- [ ] Update Python discovery to collect `EntrySpec` and `AgentSpec` instances (type-based) and enforce “exactly one entry”
- [ ] Remove `@entry` discovery and entry conflict logic from registry/discovery

### Phase 5: Delete worker.py & cleanup
- [ ] Delete `llm_do/runtime/worker.py`
- [ ] Move any needed helpers (prompt rendering, input normalization, event logging) into a new agent-runner module used by `call_agent`
- [ ] Update imports across runtime, loader, CLI, and tests

### Phase 6: Migrate tests, examples, docs
- [ ] Replace `@entry` usage with toolset factories that expose `main`
- [ ] Update tests to construct `EntrySpec` and call `Runtime.run_entry()`
- [ ] Update UI chat runner to use `Runtime.create_scope()` for multi-turn sessions
- [ ] Update CLI/docs/README/architecture references to remove `@entry` and Worker terms

## Files to Change

| File | Change |
|------|--------|
| `llm_do/runtime/contracts.py` | Add `EntrySpec`, remove `Entry` protocol |
| `llm_do/runtime/deps.py` | Add `call_agent(spec_or_name, input_data)` with depth increment |
| `llm_do/runtime/call.py` | Remove Entry coupling; keep `CallScope.call_tool` |
| `llm_do/runtime/shared.py` | Add `Runtime.create_scope()` factory, update `run_entry()` for EntrySpec |
| `llm_do/runtime/registry.py` | Build agent registry + entry selection for `EntrySpec` |
| `llm_do/runtime/discovery.py` | Discover `AgentSpec`/`EntrySpec`; remove Worker/EntryFunction |
| `llm_do/runtime/worker.py` | **DELETE ENTIRELY** |
| `llm_do/runtime/worker_file.py` | Update loader to produce `AgentSpec` + `EntrySpec` |
| `llm_do/toolsets/loader.py` | Remove Worker wrapping; toolsets only |
| `llm_do/toolsets/agent.py` | **NEW**: `agent_as_toolset()` helper |
| `llm_do/ui/runner.py` | Use `Runtime.create_scope()` for chat mode; update entry types |
| `llm_do/cli/main.py` | Accept `EntrySpec` from build_entry and runtime |

### What Happens to worker.py Contents

| Component | Disposition |
|-----------|-------------|
| `Worker` / `AgentEntry` | Removed — replaced by `AgentSpec` + `call_agent()` |
| `EntryFunction` | Removed — write toolsets with `main` directly |
| `@entry` decorator | Removed — use a toolset factory with `main` |
| `entry_from_agent()` | Removed — replaced by `agent_as_toolset(AgentSpec)` |
| `EntryToolset` | Removed — agents are toolsets; use namespacing |
| `build_entry_tool()` | Removed — not needed |
| `_DefaultEntryToolSchema` | Removed — use `main`'s signature |
| Message capture helpers | Moved into the agent-runner used by `call_agent()` |

### New Entry Pattern (No @entry)

Instead of the `@entry` decorator, users write a toolset factory with only `main`:

```python
# Before (worker.py @entry)
@entry(toolsets=[shell_spec])
async def my_worker(args, runtime):
    result = await runtime.call("helper_agent", {"input": args})
    return result

# After (entry toolset with only main)
def my_entry_toolset(ctx: ToolsetBuildContext) -> AbstractToolset:
    toolset = FunctionToolset()

    @toolset.tool
    async def main(input: str, attachments: list[str] | None = None, *, ctx) -> str:
        """Entry point. Orchestrates agents."""
        result = await ctx.deps.call_agent(helper_agent_spec, input)
        return result

    return toolset  # Only contains main

# Export a single EntrySpec instance (any name works; loaders require exactly one)
ENTRY_SPEC = EntrySpec(
    name="main",
    toolset_spec=ToolsetSpec(factory=my_entry_toolset),
)
```

## Decision Record

### Decision: Remove Entry Protocol
- **Inputs:** Desire to simplify abstractions, unify tool and entry invocation
- **Options:** (1) Keep Entry with simpler signature, (2) Remove Entry entirely
- **Outcome:** Option 2 — Entry functions become toolset functions named "main"
- **Rationale:** Uniform invocation model; everything is `call_tool`

### Decision: "main" Naming Convention
- **Inputs:** Need to identify entry point without explicit marker
- **Options:** (1) Decorator marker, (2) Naming convention, (3) Metadata in ToolsetSpec
- **Outcome:** Option 2 — Function named "main" is the entry point
- **Rationale:** Simple, familiar (like Go, C, etc.), no extra machinery

### Decision: Loader Returns ToolsetSpec, Root Uses EntrySpec
- **Inputs:** Need to preserve loader contract, but also carry entry-level metadata (name, description, schema_in)
- **Options:** (1) Loader returns instantiated toolsets, (2) Loader returns ToolsetSpec, (3) New EntrySpec wraps ToolsetSpec
- **Outcome:** Option 3 — ToolsetSpec unchanged; new `EntrySpec` carries root-level metadata
- **Rationale:** Keeps toolset loading simple; entry metadata is only needed at root invocation. Model selection is per-agent, not per-entry.

### Decision: Depth Tracking in call_agent Only
- **Inputs:** Need depth limits for LLM recursion, but call_tool shouldn't need to detect agent vs function
- **Options:** (1) call_tool detects agents, (2) call_agent is depth boundary, (3) Marker on toolsets
- **Outcome:** Option 2 — `call_agent()` increments depth; agent-as-toolset wrappers call `call_agent` internally
- **Rationale:** Keeps call_tool simple; depth logic centralized in one place

### Decision: Entry main signature
- **Inputs:** CLI input normalization uses `normalize_input` and defaults to `{input, attachments}`
- **Options:** (1) Allow arbitrary single param name, (2) Require `input` (+ optional `attachments`), (3) Add custom mapping layer
- **Outcome:** Option 2 — require `main(input, attachments=None, *, ctx)` shape
- **Rationale:** Keeps normalization predictable and avoids runtime mapping heuristics

### Decision: call_agent name lookup
- **Inputs:** Entry tools need to call `.worker` agents without importing them
- **Options:** (1) Spec-only, (2) Name-only, (3) Accept `AgentSpec | str`
- **Outcome:** Option 3 — runtime-owned registry resolves names for `call_agent`
- **Rationale:** Keeps entry code simple while preserving explicit specs for Python-defined agents

## Preserved Decisions (from v2)

| Decision | Outcome |
|----------|---------|
| Toolset instantiation | CallScope owns lifecycle (not runtime) |
| Spawn semantics | `Runtime` + `CallFrame` + `CallRuntime` architecture |
| Tool invocation | Only via `CallScope.call_tool` |
| Rename timing | Late (after architecture is stable) |

## Background (Preserved)

### What Worker Does Today
1. **Lifecycle management** — build toolsets per call, run agent, cleanup
2. **Prompt/agent orchestration** — constructing prompts, running the agent
3. **Toolset cleanup** — ensuring `cleanup()` hooks are called after runs

### Current Bug: Experiment Leaks Toolsets
The experiment's `AgentRuntime.call_agent()` builds toolsets but never cleans them up. The fix is to use CallScope lifecycle.

## Out of Scope (Deferred)

- **Experiment runtime migration** — The experiment in `experiments/pydanticai-runtime-deps/` will be updated separately after the main trunk is stable
- **WorkerRuntime → CallRuntime rename** — Deferred until after architecture is stable (per v2 decision)

## Related Documents
- `docs/notes/experiment-runtime-without-worker.md` — original analysis
- `experiments/pydanticai-runtime-deps/runtime-delta-list.md` — gap analysis
- `tasks/active/remove-worker-class-v2.md` — previous version with Entry protocol

## Possible Future Directions (Deferred)

### Tool-to-Tool Calls
We may eventually allow tools to call other tools. If/when enabled, it should
be an explicit design choice with clear semantics (approval/event wiring and
depth handling). Possible approaches:

- **Contextvar-based**: expose `call_tool` on deps (implicit current scope).
- **Explicit scope injection**: pass CallScope or a lightweight tool-caller into
  tool functions.

Until then, tools should be treated as pure functions and not invoke other
tools directly.
