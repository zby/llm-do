# SOLID Alignment Review

**Note (2026-01-26):** File paths updated for recent refactoring:
- `runtime/shared.py` → `runtime/runtime.py`
- `runtime/deps.py` → `runtime/context.py`
- `WorkerRuntime` → `CallContext`

## Context
Periodic review of SOLID alignment across the core runtime (`llm_do/runtime`),
toolsets (`llm_do/toolsets`), and the UI event/rendering stack (`llm_do/ui`).

## Review 2026-01-13

### Single Responsibility Principle

**Worker** (`runtime/worker.py`) still concentrates multiple concerns:
- Configuration (name, instructions, model, toolsets)
- Agent building (`_build_agent`)
- Execution (`call`, `_call_internal`, `_run_with_event_stream`)
- Event emission (`_emit_tool_events`)
- Toolset adapter (`as_toolset` → `WorkerToolset`)

**Runtime** (`runtime/runtime.py`) handles:
- Configuration management (`RuntimeConfig`)
- Usage tracking (`UsageCollector`)
- Message logging (`MessageAccumulator`)
- Entry execution orchestration (`run_entry`)
- Entry-scoped toolset cleanup (`_cleanup_toolsets`)

Note: Toolset cleanup is entry-scoped (toolsets are created by registry at entry
build time, cleaned up by Runtime after entry completes). This conflates entry
lifecycle management with runtime execution - cleanup could live in registry
or entry itself. Additionally, per-entry instantiation breaks isolation for
recursive worker calls (see `tasks/active/per-call-toolset-instances.md`).

**CallContext** (`runtime/context.py`) serves as:
- Tool dispatcher
- State accessor (messages, prompt, depth)
- RunContext factory
- Child runtime spawner

**UIEvent classes** (`ui/events.py`) each implement data + presentation:
- Event data fields
- `render_rich()`, `render_text()`, `create_widget()`

This "events know how to render" design was intentional but still couples
data and presentation, giving each event class multiple reasons to change.

### Open/Closed Principle

**Strengths:**
- `AbstractToolset` allows adding toolsets without modifying core
- `Entry` protocol enables new entry types
- `DisplayBackend` ABC supports new display modes
- UIEvent hierarchy allows new event types

**Weaknesses:**
- Adding a new render format requires modifying all 10+ UIEvent subclasses
- `run_entry()` has type checks for `EntryFunction` vs `Worker`

### Liskov Substitution Principle

**No major violations.** Subtypes behave correctly:
- `ReadOnlyFileSystemToolset` properly restricts `FileSystemToolset`
- `WorkerToolset` correctly adapts `Worker` for toolset contexts
- All `DisplayBackend` implementations are interchangeable

Previous concern about `Worker` as toolset is resolved: Worker no longer
inherits from `AbstractToolset`; it uses `WorkerToolset` adapter instead.

### Interface Segregation Principle

**Strengths:**
- `Entry` protocol is minimal (name, toolsets, input_model)
- `DisplayBackend` is focused (display, start, stop)
- Controllers are narrowly scoped

**Weaknesses:**
- `WorkerRuntimeProtocol` exposes ~15 properties; simpler tools may not need all
- UIEvent mandates all render methods even if a format is unused

### Dependency Inversion Principle

**Persistent violation - runtime → ui coupling:**

```
runtime/contracts.py:15  → from ..ui.events import UIEvent
runtime/worker.py:37     → from ..ui.events import ToolCallEvent, ToolResultEvent
runtime/runtime.py:14     → from ..ui.events import UserMessageEvent
runtime/context.py:212      → from ..ui.events import ToolCallEvent, ToolResultEvent
```

High-level runtime modules depend on low-level UI event types. This inverts
the expected dependency direction and means runtime changes may break UI
and vice versa.

**Good practices:**
- Approval uses callbacks (abstraction)
- Toolsets use `AbstractToolset`
- Display uses `DisplayBackend` ABC

### Summary vs Previous Review (2026-01-13)

| Issue | Status |
|-------|--------|
| Runtime↔UI coupling (DIP) | **Persists** - contracts.py, worker.py still import ui.events |
| Worker multi-responsibility (SRP) | **Persists** - input, agent, streaming, events |
| UI events render-centric (OCP/ISP) | **Persists** - all events implement all render methods |
| Worker as toolset (LSP) | **Resolved** - now uses WorkerToolset adapter |

### Recommendations (2026-01-13)

1. **Decouple runtime from UI events:** Define a lightweight `RuntimeEvent`
   protocol in runtime layer; let UI layer translate to `UIEvent` types.

2. **Extract Worker concerns:** Split into InputNormalizer, AgentRunner,
   StreamHandler collaborators.

3. **Move rendering to backends:** Use visitor/strategy pattern so new
   formats don't require editing all event classes.

4. **Slim WorkerRuntimeProtocol:** Consider splitting into smaller interfaces
   for tools that need less.

### Files Reviewed (2026-01-13)
- `llm_do/runtime/__init__.py`, `shared.py`, `deps.py`, `worker.py`, `call.py`, `contracts.py`, `approval.py`
- `llm_do/ui/events.py`, `display.py`, `parser.py`, `runner.py`, `app.py`
- `llm_do/toolsets/__init__.py`, `filesystem.py`

## Review 2026-01-15

### Single Responsibility Principle

**Worker** (`runtime/worker.py`) still bundles many concerns and has grown further:
- Input normalization + prompt construction
- Attachment resolution (path normalization + tool calls)
- Toolset plane assembly + approval wrapping
- Agent construction + execution
- Streaming event handling + fallback tool event emission
- Message logging (incremental log capture)

**Runtime** (`runtime/runtime.py`) still aggregates multiple responsibilities:
- Configuration and policy wiring
- Usage + message log collection
- Entry dispatch (`run_entry`)
- Toolset lifecycle orchestration (call-scope cleanup via `runtime/call.py (toolset cleanup inlined)`)

**CallContext** (`runtime/context.py`) continues as the "god object":
- Tool dispatch + arg validation
- RunContext construction
- Usage tracking
- Event emission
- Child runtime spawning

**UIEvent classes** still mix data + rendering (Rich/Text/Textual).

### Open/Closed Principle

**Strengths:**
- `ToolsetDef` + DynamicToolset factories keep toolset creation extensible
- `parse_event()` centralizes raw PydanticAI event parsing

**Weaknesses:**
- New entry types still require editing `Runtime.run_entry()` (type checks)
- New render formats require touching every `UIEvent` subclass
- `UIEvent` additions require updates in parser + widgets + display

### Liskov Substitution Principle

**No new violations observed.**
- `WorkerToolset` adapter remains the correct substitution for toolset contexts
- `ApprovalDeniedResultToolset` continues to delegate to inner toolsets

### Interface Segregation Principle

**Persistent issues:**
- `WorkerRuntimeProtocol` is still wide (~15+ properties/methods)
- `UIEvent` enforces render methods even for modes that may not be used

### Dependency Inversion Principle

**Still inverted at runtime/UI boundary:**

```
runtime/contracts.py → UIEvent (callback type)
runtime/runtime.py    → UserMessageEvent
runtime/worker.py    → ToolCallEvent, ToolResultEvent, parse_event()
runtime/context.py      → ToolCallEvent, ToolResultEvent
```

Runtime layers still import UI types and emit UI-specific events directly.
The coupling now includes both event type dependencies and parsing helpers,
keeping UI as a "low-level detail" in core runtime execution.

### Summary vs Previous Review (2026-01-15)

| Issue | Status |
|-------|--------|
| Runtime↔UI coupling (DIP) | **Persists** - runtime still imports/emits UI events |
| Worker multi-responsibility (SRP) | **Persists** - attachments + message logging added to worker scope |
| UI events render-centric (OCP/ISP) | **Persists** - format changes require per-event edits |
| Worker as toolset (LSP) | **Still resolved** - adapter pattern remains intact |
| Event parsing centralization | **Stable** - parser remains the single choke point |

### Recommendations (2026-01-15)

1. **Decouple runtime from UI events:** Introduce a runtime-layer event protocol and let UI adapt.
2. **Extract Worker concerns:** Split into InputNormalizer, AgentRunner, StreamHandler.
3. **Move rendering to backends:** Use visitor/strategy for UI formats.
4. **Slim WorkerRuntimeProtocol:** Break into smaller interfaces for tools.
5. **Extract attachment resolution:** Move path resolution + attachment fetching into a dedicated component/toolset.

### Files Reviewed (2026-01-15)
- `llm_do/runtime/worker.py`, `shared.py`, `deps.py`, `contracts.py`, `approval.py`, `call.py`
- `llm_do/toolsets/loader.py`
- `llm_do/ui/events.py`, `parser.py`

## Review 2026-01-17

### Single Responsibility Principle

**Worker** (`runtime/worker.py`) still concentrates multiple concerns:
- Input normalization + prompt construction
- Attachment resolution + file IO
- Toolset assembly + approval wrapping
- Agent construction + execution
- Event streaming + fallback tool event emission
- Message logging (incremental + final snapshots)

**CallContext** (`runtime/context.py`) remains a central orchestrator:
- Tool discovery + dispatch
- RunContext construction + usage tracking
- Tool event emission
- Call-frame state management + child runtime spawning

**Runtime** (`runtime/runtime.py`) still aggregates config, usage, message
logging, and entry dispatch. Toolset cleanup is now owned by `CallScope`
via `runtime/call.py (toolset cleanup inlined)`, which reduces cross-cutting concerns here.

**UIEvent classes** (`ui/events.py`) continue to mix data + rendering
(Rich/Text/Textual widget creation).

### Open/Closed Principle

**Strengths:**
- `Runtime.run_entry()` now relies on `Entry.start()` instead of type checks
- Runtime events are now a stable core API (`runtime/events.py`)
- `ToolsetDef` (TOOLSETS registry) continues to allow toolset extension without modifying runtime

**Weaknesses:**
- New runtime event types require updates in `ui/adapter.py`
- `UIEvent` additions still require edits per render method
- `run_tui()` still uses `isinstance(entry_instance, Worker)` for chat mode,
  so new entry types must modify UI runner logic to participate

### Liskov Substitution Principle

**No major violations observed.**
- `WorkerToolset` remains an adapter, not a subtype
- `EntryFunction` and `Worker` satisfy `Entry` protocol expectations

### Interface Segregation Principle

**Improved:**
- `WorkerRuntimeProtocol` is now slim (config + frame + logging + spawn_child)

**Persistent issues:**
- `UIEvent` mandates all render/create methods even if a backend never uses them

### Dependency Inversion Principle

**Resolved at runtime/UI boundary:**

```
runtime/events.py defines RuntimeEvent types
ui/adapter.py adapts RuntimeEvent → UIEvent
runtime no longer imports ui.*
```

Runtime now depends on its own event types; UI depends on runtime events, which
restores the intended dependency direction.

### Summary vs Previous Review (2026-01-15)

| Issue | Status |
|-------|--------|
| Runtime↔UI coupling (DIP) | **Resolved** - runtime emits RuntimeEvent; UI adapts |
| Worker multi-responsibility (SRP) | **Persists** - attachments, logging, streaming remain |
| UI events render-centric (OCP/ISP) | **Persists** - per-event render methods required |
| WorkerRuntimeProtocol too wide (ISP) | **Improved** - narrowed to core runtime surface |
| run_entry type checks (OCP) | **Resolved** - `Entry.start()` dispatch |
| UI runner Worker type checks (OCP) | **Persists** - chat path still Worker-only |

### Recommendations (2026-01-17)

1. **Extract Worker concerns:** Move attachments, message logging, and event
   streaming into collaborators (InputNormalizer, AttachmentLoader, StreamHandler).
2. **Split CallContext responsibilities:** Separate tool dispatch from runtime
   state/usage bookkeeping.
3. **Decouple UI rendering from events:** Shift render logic to backend-specific
   visitors/strategies so new formats don't touch every event class.
4. **Add a chat capability contract:** Replace `isinstance(Worker)` checks in
   UI runner with an interface or capability flag.

### Files Reviewed (2026-01-17)
- `llm_do/runtime/events.py`, `event_parser.py`, `worker.py`, `deps.py`, `shared.py`, `call.py`, `contracts.py`, `toolsets.py`
- `llm_do/toolsets/loader.py`
- `llm_do/ui/adapter.py`, `events.py`, `runner.py`, `display.py`

## Review 2026-01-24

### Single Responsibility Principle

**Worker** no longer exists as a monolith, and responsibilities are now spread across:
- `runtime/agent_runner.py` (agent construction + execution + event streaming)
- `runtime/context.py` (call-scoped runtime orchestration)
- `runtime/worker_file.py` (worker file parsing)
- `runtime/registry.py` (spec construction + toolset wiring)

This is a clear SRP improvement over the prior all-in-one Worker class.

**CallContext** (`runtime/context.py`) is still a "central orchestrator" that owns:
- tool dispatch + arg validation
- toolset instantiation + approval wrapping
- call-frame spawning + depth enforcement
- event emission for tool calls/results
- usage + message logging integration

That breadth means many reasons to change live in one class. It is coherent as the
runtime "engine," but it still blends policy (approval, logging, events) with
mechanics (tool invocation, call frames).

**AgentRunner** (`runtime/agent_runner.py`) handles:
- prompt normalization + rendering
- agent construction
- event stream parsing + emission
- message logging (incremental and final)

This is cohesive but still mixes "run the model" with "translate/emit events."
The fallback tool-event emission logic also duplicates some behavior in
`CallContext._call_tool`.

**Runtime** (`runtime/runtime.py`) bundles configuration, usage collection, message
logging, and entry dispatch. That is arguably the right aggregate for a shared
runtime, but it remains multi-purpose.

### Open/Closed Principle

**Strengths:**
- `EntrySpec` is now the single entry surface; `Runtime.run_entry()` no longer
  type-checks concrete entry implementations.
- `ToolsetDef` factories allow new toolsets without touching runtime core.
- `RuntimeEvent` + `ui/adapter.py` provides a clear extension point.

**Weaknesses:**
- Adding a new render format requires adding methods to `UIEvent` and updating
  every subclass.
- `ui/adapter.py` requires updates for every new `RuntimeEvent` type.
- Built-in tool factories are hard-coded in `runtime/registry.py` — new builtin
  tool types require modifying core runtime code.

### Liskov Substitution Principle

**No major violations observed.** Adapters preserve expected substitution:
- `AgentToolset` wraps `AgentSpec` cleanly as a toolset.
- `ApprovalDeniedResultToolset` preserves the `AbstractToolset` interface.

One caveat: `ApprovalDeniedResultToolset` deliberately converts `PermissionError`
into a dict result, which changes error semantics. This is intentional but worth
documenting as a behavioral shift for callers expecting exceptions.

### Interface Segregation Principle

**Improved:**
- `WorkerRuntimeProtocol` is now genuinely minimal and focused.

**Persistent issues:**
- `UIEvent` forces all events to implement `render_rich`, `render_text`, and
  `create_widget`, even when only one backend needs a given method.

### Dependency Inversion Principle

**Resolved at runtime/UI boundary:**
- Runtime depends only on `RuntimeEvent` types; UI depends on runtime via
  `ui/adapter.py`.

**Remaining coupling (acceptable but notable):**
- `runtime/event_parser.py` and `runtime/agent_runner.py` depend directly on
  PydanticAI event types. Swapping the underlying model library would require
  changes in runtime core, not just adapters.

### Summary vs Previous Review (2026-01-17)

| Issue | Status |
|-------|--------|
| Runtime↔UI coupling (DIP) | **Still resolved** - runtime emits `RuntimeEvent` |
| Worker multi-responsibility (SRP) | **Improved** - Worker split into smaller modules |
| UI events render-centric (OCP/ISP) | **Persists** - render methods still on events |
| WorkerRuntimeProtocol too wide (ISP) | **Still improved** - narrow surface remains |
| UI runner Worker-only checks (OCP) | **Resolved** - chat path uses EntrySpec |

### Recommendations (2026-01-24)

1. **Split CallContext responsibilities:** Introduce collaborators for
   tool invocation (arg validation + event emission) and call lifecycle
   (toolset instantiation + cleanup). This isolates policy decisions from
   mechanics. Trade-off: more indirection and objects to wire.
2. **Centralize tool-event emission:** Move `_emit_tool_events` and
   `_call_tool` event emission behind a shared event emitter so tool call
   telemetry has a single source of truth. Trade-off: more coordination
   between agent runner and runtime.
3. **Move rendering out of UIEvent:** Use visitor/strategy renderers
   (`RichRenderer`, `TextRenderer`, `WidgetFactory`) that operate on plain
   event data. This reduces ISP violations and makes new output formats
   additive. Trade-off: slightly more boilerplate wiring.
4. **Make builtin tool factories extensible:** A registry hook or config-driven
   mapping would allow new builtin tools without editing `runtime/registry.py`.
   Trade-off: less explicit control and slightly harder tracing.

### Files Reviewed (2026-01-24)
- `llm_do/runtime/agent_runner.py`, `deps.py`, `shared.py`, `registry.py`, `call.py`, `contracts.py`, `event_parser.py`, `events.py`, `args.py`
- `llm_do/runtime/worker_file.py`, `discovery.py`
- `llm_do/toolsets/agent.py`, `toolsets/loader.py`, `toolsets/builtins.py`, `toolsets/approval.py`
- `llm_do/ui/events.py`, `adapter.py`, `display.py`, `runner.py`, `controllers/worker_runner.py`

## Review 2026-01-29

### Single Responsibility Principle

**AgentSpec** (`runtime/contracts.py`) is now a clean configuration dataclass:
- Stores agent configuration (name, instructions, model, toolsets)
- Validation in `__post_init__`
- No execution logic

**Call State Hierarchy** (`runtime/call.py`) shows excellent separation:
- `CallConfig` — immutable per-call configuration
- `CallFrame` — mutable call-scoped state (prompt, messages)
- `CallScope` — lifecycle management (toolset instantiation, cleanup)

**CallContext** (`runtime/context.py`) remains the central orchestrator:
- Tool dispatch + arg validation
- RunContext construction + usage tracking
- Event emission
- Child runtime spawning

This breadth is intentional as the runtime "engine," but blends policy
(approval, logging, events) with mechanics (tool invocation, frames).

**Runtime** (`runtime/runtime.py`) aggregates:
- Configuration management (`RuntimeConfig`)
- Thread-safe usage tracking (`UsageCollector`)
- Thread-safe message logging (`MessageAccumulator`)
- Entry dispatch orchestration

**AgentRunner** (`runtime/agent_runner.py`) handles:
- Agent construction via PydanticAI
- Event stream parsing + emission
- Message logging

### Open/Closed Principle

**Strengths:**
- `Entry` hierarchy (Entry → FunctionEntry/AgentEntry) allows new entry types
  without modifying runtime core
- `ToolsetDef` factories enable new toolsets via `AbstractToolset` inheritance
- `register_model_factory()` in `models.py` allows custom provider registration
- Approval callbacks are pluggable strategies
- `RuntimeEvent` + `ui/adapter.py` provides clear extension point

**Weaknesses:**
- Adding new render format requires modifying all `UIEvent` subclasses
- `ui/adapter.py` requires updates for every new `RuntimeEvent` type
- Built-in tool factories are hard-coded in `toolsets/builtins.py`

### Liskov Substitution Principle

**No major violations observed.**
- `FunctionEntry` and `AgentEntry` satisfy `Entry.run()` contract equally
- `ReadOnlyFileSystemToolset` properly specializes `FileSystemToolset`
- All `AbstractToolset` implementations are interchangeable
- `AgentToolset` correctly adapts `AgentSpec` for toolset contexts
- `ApprovalDeniedResultToolset` preserves `AbstractToolset` interface

### Interface Segregation Principle

**Strengths:**
- `CallContextProtocol` is minimal (config, frame, log_messages, spawn_child, call_agent)
- Approval-related types segregated in `runtime/approval.py`
- Separate types for runtime vs. manifest config

**Weaknesses:**
- `AbstractToolset` has a broad interface (get_tools, call_tool, needs_approval,
  get_approval_description, get_capabilities)
- `UIEvent` mandates all render methods even if a backend never uses them

### Dependency Inversion Principle

**Resolved at runtime/UI boundary:**
- Runtime depends only on `RuntimeEvent` types (`runtime/events.py`)
- UI depends on runtime via `ui/adapter.py`
- Runtime no longer imports `ui.*`

**Good practices observed:**
- `CallContextProtocol` allows depending on abstraction, not concrete `CallContext`
- Approval callbacks are function-based (not tied to implementations)
- Toolsets depend on `AbstractToolset` abstraction
- Forward declarations via `TYPE_CHECKING` avoid circular dependencies

**Remaining coupling (acceptable):**
- `runtime/agent_runner.py` depends on PydanticAI event types directly

### Summary vs Previous Review (2026-01-24)

| Issue | Status |
|-------|--------|
| UI events render-centric (OCP/ISP) | **Persists** - render methods still on events |
| CallContext multi-responsibility (SRP) | **Persists** - policy + mechanics combined |

### Recommendations (2026-01-29)

1. **Split CallContext responsibilities:** Extract tool invocation mechanics
   (arg validation, dispatch) from policy decisions (approval, event emission).
   Trade-off: more indirection.

2. **Move rendering out of UIEvent:** Use visitor/strategy renderers so new
   output formats don't touch every event class. Trade-off: more wiring.

3. **Make builtin toolsets extensible:** Registry hook or plugin pattern for
   `toolsets/builtins.py`. Trade-off: less explicit control.

4. **Consider narrowing AbstractToolset:** Split into focused interfaces
   (ToolProvider, ApprovalChecker, CapabilityDescriber). Trade-off: more types
   to manage.

### Files Reviewed (2026-01-29)
- `llm_do/runtime/contracts.py`, `runtime.py`, `context.py`, `call.py`, `agent_runner.py`
- `llm_do/runtime/approval.py`, `registry.py`, `discovery.py`, `entry_resolver.py`, `manifest.py`
- `llm_do/runtime/agent_file.py`, `args.py`, `events.py`
- `llm_do/toolsets/loader.py`, `builtins.py`, `filesystem.py`, `shell/toolset.py`
- `llm_do/toolsets/agent.py`, `dynamic_agents.py`, `approval.py`
- `llm_do/models.py`
- `llm_do/ui/events.py`, `adapter.py`
