# UI and TUI Review

## Context
Review of Textual TUI widgets/app, display backends, and UI docs for correctness and consistency.

## Findings
- `docs/ui.md` describes a RichDisplayBackend and omits `approval_request` events, but the code uses Textual and includes approval events. The doc is stale relative to current UI architecture.
- `ToolResultMessage` renders `result.content` but `ToolReturnEvent` exposes `result` instead; tool results in live event mode may show no payload content.
- `_update_approval_bindings` is effectively a no-op; bindings are never shown/hidden based on approval state, making the UI feedback incomplete.
- `DisplayBackend.handle_event` has no explicit branch for `approval_request`; if that event ever flows through a backend, it will be misrouted to `display_runtime_event`.

## Analysis
- Documentation drift makes it harder to maintain the UI and to onboard contributors, especially when the backend is now Textual-focused.
- The tool result mismatch can lead to blank or misleading output in live TUI mode, which undermines trust in tool execution feedback.
- Dead approval binding code suggests either unfinished UX or an abandoned feature; either way it adds confusion.
- Missing `approval_request` handling is a latent bug that can surface once approval events reach the display layer.

## Possible Fixes
- Update `docs/ui.md` to reflect the Textual backend and include approval event handling.
- Adjust `ToolResultMessage` to render `ToolReturnEvent.result` (or both `result` and `content` paths) for consistency.
- Either implement `_update_approval_bindings` properly or remove the dead code to reduce maintenance overhead.
- Add an explicit `approval_request` branch in `DisplayBackend.handle_event` to route to the correct display logic.

## Recommendations
1. Refresh `docs/ui.md` to match the Textual architecture and current event types.
2. Fix tool result rendering to avoid empty payload displays in live mode.
3. Implement or remove approval binding toggling to keep UX consistent and reduce dead code.
4. Add explicit `approval_request` handling in display backends.

## Open Questions
- Should tool result rendering handle `ToolReturnEvent.result` explicitly to avoid empty displays?
- Should approval binding toggling be implemented or removed to reduce dead code?
- Should UI docs be updated to match the Textual backend and event kinds?

## Conclusion
The UI issues are mostly consistency and visibility problems. Updating docs and rendering paths will reduce confusion, while cleaning approval-related code will make the TUI behavior more predictable.
