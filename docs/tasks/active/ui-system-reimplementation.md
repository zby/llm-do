# UI System Reimplementation

## Prerequisites
- [x] none

## Goal
Reimplement the UI system according to `docs/notes/ui-specification.md` so that events know how to render themselves, parsing is centralized, and the TUI app becomes a thin consumer.

## Reference
See `docs/notes/ui-specification.md` for full specification including:
- Event type hierarchy and render methods
- Parser implementation
- Display backend interfaces
- Widget specifications
- CLI integration patterns

## Tasks

### Phase 1: Core Event System
Create `llm_do/ui/events.py` with typed event classes:
- [x] `UIEvent` base class with abstract `render_rich()`, `render_text()`, `render_json()`, `create_widget()` methods
- [x] `InitialRequestEvent` - worker receives initial request
- [x] `StatusEvent` - phase/state transitions
- [x] `TextResponseEvent` - model text responses (streaming and complete)
- [x] `ToolCallEvent` - tool invocations
- [x] `ToolResultEvent` - tool execution results
- [x] `DeferredToolEvent` - async tool status updates
- [x] `CompletionEvent` - worker completion
- [x] `ErrorEvent` - error display
- [x] `ApprovalRequestEvent` - interactive approval requests

### Phase 2: Parser
Create `llm_do/ui/parser.py`:
- [x] `_extract_delta_content()` helper for PartDeltaEvent
- [x] `parse_event()` function - single point for pydantic-ai type inspection
- [x] Unit tests for each event type conversion

### Phase 3: Display Backends
Create/update `llm_do/ui/display.py`:
- [x] `DisplayBackend` abstract base class with `start()`, `stop()`, `display()` methods
- [x] `RichDisplayBackend` - Rich Console output with verbosity support
- [x] `HeadlessDisplayBackend` - Plain ASCII text (no ANSI codes)
- [x] `JsonDisplayBackend` - JSONL for automation
- [x] `TextualDisplayBackend` - Queue forwarding for TUI

### Phase 4: Widgets
Create/update `llm_do/ui/widgets/messages.py`:
- [x] `BaseMessage(Static)` - base widget class
- [x] `AssistantMessage` with `append_text()` and `set_text()` for streaming
- [x] `ToolCallMessage` - tool invocation display
- [x] `ToolResultMessage` - tool result display
- [x] `StatusMessage` - status updates
- [x] `ErrorMessage` - error display
- [x] `ApprovalMessage` - interactive approval requests
- [x] `MessageContainer` with `handle_event()` for routing

### Phase 5: TUI Application
Update `llm_do/ui/app.py`:
- [x] Remove `_handle_runtime_event()` method
- [x] Remove `_handle_dict_event()` method
- [x] Remove `_handle_deferred_tool()` method
- [x] Remove all `if event.kind == "..."` branching
- [x] Remove all `hasattr()` checks for payload inspection
- [x] Implement typed `_consume_events()` loop
- [x] Add `_handle_event_state()` for special state management
- [x] Add error handling around `event.create_widget()`

### Phase 6: CLI Integration
- [x] Update CLI to use `parse_event()` in message callbacks
- [x] Verify TUI mode captures to buffers correctly (events->stderr, result->stdout)
- [x] Verify headless/rich modes write to stderr
- [x] Verify final result goes to stdout

### Phase 7: Testing
- [x] Unit tests for each event's render methods
- [x] Unit tests for parser event type conversion
- [ ] Integration test: TUI mode end-to-end (requires manual testing)
- [ ] Integration test: Headless mode end-to-end (requires manual testing)
- [ ] Integration test: Rich mode end-to-end (requires manual testing)
- [ ] Integration test: JSON mode end-to-end (requires manual testing)
- [ ] Integration test: Approval flow in TUI (requires manual testing)
- [ ] Integration test: Error handling display (requires manual testing)

## Current State
Implementation complete. All core functionality implemented:
- Created `llm_do/ui/events.py` with 10 typed UIEvent classes
- Created `llm_do/ui/parser.py` with centralized event parsing
- Updated `llm_do/ui/display.py` with simplified backends that call event.render_*()
- Updated `llm_do/ui/widgets/messages.py` with ErrorMessage and handle_event()
- Updated `llm_do/ui/app.py` to be a thin consumer using typed events
- Updated `llm_do/cli_async.py` to use parse_event() in callbacks
- Updated `llm_do/ui/__init__.py` with new exports
- Updated tests in `tests/test_display_backends.py` with new test cases

All 238 tests pass.

## Notes
- This supersedes `ui-event-cleanup.md` which covers a subset of this work
- Key principle: "Events Know How to Render Themselves" - no backend inspection of payloads
- Output streams: events->stderr, final result->stdout (enables piping)
- Verbosity levels: 0=minimal, 1=normal, 2=verbose (streaming deltas)
- Integration tests for TUI/approval flow require manual testing or headless Textual testing framework
