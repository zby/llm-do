# SOLID Alignment Review

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

**Runtime** (`runtime/shared.py`) handles:
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

**WorkerRuntime** (`runtime/deps.py`) serves as:
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
- `Entry` protocol is minimal (name, toolsets, schema_in)
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
runtime/shared.py:14     → from ..ui.events import UserMessageEvent
runtime/deps.py:212      → from ..ui.events import ToolCallEvent, ToolResultEvent
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

**Runtime** (`runtime/shared.py`) still aggregates multiple responsibilities:
- Configuration and policy wiring
- Usage + message log collection
- Entry dispatch (`run_entry`)
- Toolset lifecycle orchestration (call-scope cleanup via `runtime/toolsets.py`)

**WorkerRuntime** (`runtime/deps.py`) continues as the "god object":
- Tool dispatch + arg validation
- RunContext construction
- Usage tracking
- Event emission
- Child runtime spawning

**UIEvent classes** still mix data + rendering (Rich/Text/Textual).

### Open/Closed Principle

**Strengths:**
- `ToolsetSpec` + `instantiate_toolsets` keep toolset creation extensible
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
runtime/shared.py    → UserMessageEvent
runtime/worker.py    → ToolCallEvent, ToolResultEvent, parse_event()
runtime/deps.py      → ToolCallEvent, ToolResultEvent
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

**WorkerRuntime** (`runtime/deps.py`) remains a central orchestrator:
- Tool discovery + dispatch
- RunContext construction + usage tracking
- Tool event emission
- Call-frame state management + child runtime spawning

**Runtime** (`runtime/shared.py`) still aggregates config, usage, message
logging, and entry dispatch. Toolset cleanup is now owned by `CallScope`
via `runtime/toolsets.py`, which reduces cross-cutting concerns here.

**UIEvent classes** (`ui/events.py`) continue to mix data + rendering
(Rich/Text/Textual widget creation).

### Open/Closed Principle

**Strengths:**
- `Runtime.run_entry()` now relies on `Entry.start()` instead of type checks
- Runtime events are now a stable core API (`runtime/events.py`)
- `ToolsetSpec` continues to allow toolset extension without modifying runtime

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
2. **Split WorkerRuntime responsibilities:** Separate tool dispatch from runtime
   state/usage bookkeeping.
3. **Decouple UI rendering from events:** Shift render logic to backend-specific
   visitors/strategies so new formats don't touch every event class.
4. **Add a chat capability contract:** Replace `isinstance(Worker)` checks in
   UI runner with an interface or capability flag.

### Files Reviewed (2026-01-17)
- `llm_do/runtime/events.py`, `event_parser.py`, `worker.py`, `deps.py`, `shared.py`, `call.py`, `contracts.py`, `toolsets.py`
- `llm_do/toolsets/loader.py`
- `llm_do/ui/adapter.py`, `events.py`, `runner.py`, `display.py`
