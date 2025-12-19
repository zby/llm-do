# Textual UI Consistency Fixes

## Idea
Align UI docs and event handling with the current Textual backend and fix tool result rendering.

## Why
Docs drift and mismatched event rendering reduce trust in the TUI and make tool feedback unreliable.

## Rough Scope
- Update `docs/ui.md` to reflect the Textual backend and approval events.
- Render `ToolReturnEvent.result` in `ToolResultMessage` (or support both paths).
- Implement or remove `_update_approval_bindings` to avoid dead UX code.
- Handle `approval_request` explicitly in display backends.

## Why Not Now
Requires UI testing and coordination with any ongoing TUI work.

## Trigger to Activate
Planned TUI improvements or reports of missing tool result output.
