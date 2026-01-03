# Textual UI Consistency Fixes

## Prerequisites
- [x] None.

## Goal
Textual UI docs and event handling align with current backend behavior.

## Tasks
- [x] Update `docs/ui.md` to reflect the Textual backend and approval events.
- [x] Render `ToolReturnEvent.result` in tool result views (or support both paths).
- [x] Implement or remove `_update_approval_bindings` to avoid dead UX code.
- [x] Handle `approval_request` explicitly in display backends.

## Current State
Completed.

## Notes
- Origin: UI/TUI review notes.

## Implementation Summary

1. **docs/ui.md updates**:
   - Changed `RichDisplayBackend` references to `TextualDisplayBackend`
   - Added `approval_request` to CLIEvent kinds
   - Documented that approval handling is TUI-only (non-interactive backends
     require --approve-all or --strict)

2. **ToolReturnEvent handling**:
   - Removed dead `"ToolReturnEvent"` branch from `_handle_runtime_event`
     (this event type doesn't exist in pydantic-ai)
   - Tool results correctly flow through `_handle_dict_event` →
     `FunctionToolResultEvent` → `event.result` (a ToolReturnPart with .content)

3. **_update_approval_bindings removal**:
   - Removed the no-op function (loop with `pass` body)
   - Removed all calls from action_approve, action_approve_session, action_deny

4. **approval_request in display backends**:
   - Documented as TUI-only in docs/ui.md
   - LlmDoApp handles directly via event loop, bypasses DisplayBackend abstraction
