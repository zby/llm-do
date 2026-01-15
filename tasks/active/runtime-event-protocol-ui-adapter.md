# Runtime Event Protocol + UI Adapter

## Status
ready for implementation

## Prerequisites
- [x] design decision needed (runtime event surface + adapter boundary)

## Goal
Define a runtime-layer event protocol and a UI adapter so runtime modules no longer depend on `llm_do.ui` event types.

## Context
- Relevant files/symbols: `llm_do/runtime/contracts.py`, `llm_do/runtime/worker.py`, `llm_do/runtime/shared.py`, `llm_do/runtime/deps.py`, `llm_do/ui/events.py`, `llm_do/ui/parser.py`, `llm_do/ui/runner.py`, `llm_do/ui/display.py`
- Related tasks/notes/docs: `docs/notes/reviews/review-solid.md` (background only; core findings are inlined below)
- Current coupling snapshot (from SOLID review):
  - Runtime depends on UI types: `runtime/contracts.py` (`EventCallback` uses `UIEvent`), `runtime/shared.py` (`UserMessageEvent`), `runtime/worker.py` (`ToolCallEvent`, `ToolResultEvent`, `parse_event()`), `runtime/deps.py` (`ToolCallEvent`, `ToolResultEvent`).
  - Runtime emits UI-specific events directly, keeping UI as a low-level detail in core execution flow.
  - `parse_event()` lives in `llm_do/ui/parser.py`; runtime should not call it once adapter exists.
- How to verify / reproduce:
  - `rg -n "llm_do\\.ui" llm_do/runtime` returns no hits after refactor
  - `rg -n "parse_event" llm_do/runtime` returns no hits after refactor
  - `EventCallback` in `llm_do/runtime/contracts.py` uses a runtime-layer event type
  - UI still renders by adapting runtime events to `UIEvent` (adapter path only)
  - Tests updated for runtime events + adapter mapping (`tests/runtime/test_events.py`, `tests/test_display_backends.py`)
  - `uv run pytest` (and `uv run mypy llm_do` if typing is touched) pass

## Decision Record
- Decision: runtime event protocol includes streaming deltas; UI adapter lives in `llm_do/ui/adapter.py` and is stateless
- Inputs: SOLID review notes on runtime/UI coupling and event handling
- Options:
  - Define runtime events as dataclasses in `llm_do/runtime/events.py` and have UI adapt
  - Use a light Protocol or `TypedDict` event envelope to keep runtime minimal
  - Keep raw PydanticAI events in runtime and move parsing entirely into UI adapter
- Outcome: choose runtime dataclasses with delta events + new stateless adapter module
- Follow-ups: document chosen event surface, streaming policy, and adapter responsibilities in this task

## Tasks
- [x] Decide runtime event surface, streaming delta handling, and adapter placement
- [ ] Inventory event emission sites and map to runtime event types
- [ ] Add runtime-layer event definitions and update `EventCallback` typing
- [ ] Update runtime code to emit runtime events and remove UI imports
- [ ] Implement UI adapter that maps runtime events to `UIEvent`
- [ ] Update UI runner/display wiring to use the adapter
- [ ] Update/extend tests for runtime event emission + UI adapter mapping
- [ ] Update docs/notes with final decisions and rationale

## Current State
Task updated with tighter verification and inline coupling details. Decisions made: runtime events include deltas; stateless adapter lives in `llm_do/ui/adapter.py`. Ready for implementation.

## Notes
- Trade-off: richer runtime events improve UI clarity but risk UI-specific leakage into runtime.
- Keep the adapter in UI so runtime stays unaware of rendering concerns.
- Resolved: runtime events preserve streaming deltas; adapter is stateless in `llm_do/ui/adapter.py`.
