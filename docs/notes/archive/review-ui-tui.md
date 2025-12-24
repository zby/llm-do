# UI and TUI Review

## Context
Review of Textual TUI widgets/app, display backends, and UI docs for correctness and consistency.

## Findings
- `docs/ui.md` still describes a Rich-first backend and omits the current `UIEvent` + Textual approval flow, so it is stale relative to the DisplayBackend + `LlmDoApp` architecture.
- No other mismatches found: tool results are normalized in `ToolResultEvent`, and approvals are handled directly by `LlmDoApp` via the approval queue.

## Analysis
- Documentation drift makes it harder to maintain the UI and to onboard contributors, especially when the backend is now Textual-focused.

## Possible Fixes
- Update `docs/ui.md` to reflect the Textual backend, the `UIEvent` parser, and approval handling in `LlmDoApp`.

## Recommendations
1. Refresh `docs/ui.md` to match the Textual architecture and current event types.

## Open Questions
- Should UI docs be updated to match the Textual backend and event kinds?

## Conclusion
The remaining UI issue is documentation drift. Updating the docs to match the current
DisplayBackend + `UIEvent` pipeline will reduce confusion and onboarding friction.
