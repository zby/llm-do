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

## Summary vs Previous Review

| Issue | Status |
|-------|--------|
| Runtime↔UI coupling (DIP) | **Persists** - contracts.py, worker.py still import ui.events |
| Worker multi-responsibility (SRP) | **Persists** - input, agent, streaming, events |
| UI events render-centric (OCP/ISP) | **Persists** - all events implement all render methods |
| Worker as toolset (LSP) | **Resolved** - now uses WorkerToolset adapter |

## Recommendations (unchanged)

1. **Decouple runtime from UI events:** Define a lightweight `RuntimeEvent`
   protocol in runtime layer; let UI layer translate to `UIEvent` types.

2. **Extract Worker concerns:** Split into InputNormalizer, AgentRunner,
   StreamHandler collaborators.

3. **Move rendering to backends:** Use visitor/strategy pattern so new
   formats don't require editing all event classes.

4. **Slim WorkerRuntimeProtocol:** Consider splitting into smaller interfaces
   for tools that need less.

## Files Reviewed
- `llm_do/runtime/__init__.py`, `shared.py`, `deps.py`, `worker.py`, `call.py`, `contracts.py`, `approval.py`
- `llm_do/ui/events.py`, `display.py`, `parser.py`, `runner.py`, `app.py`
- `llm_do/toolsets/__init__.py`, `filesystem.py`
