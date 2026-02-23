# Simplify: ui/widgets/

## Context
Review of Textual message widgets in `ui/widgets/messages.py`.

## Findings
- Tool call/result formatting logic is duplicated across `ToolCallMessage`,
  `ToolResultMessage`, and `ui.events` renderers. A shared formatter would keep
  text and TUI output consistent.
- `MessageContainer` has many small `add_*` helpers that mostly mount a widget
  and scroll. Consider a single `mount_message()` helper that accepts a widget
  to reduce repeated code.
- `_format_approval_request()` builds the same strings that `ApprovalRequestEvent`
  renders in headless mode. Consider sharing formatting to avoid drift.

## 2026-02-09 Review
- Tool call/result formatting duplicates UI event formatting logic; extracting shared formatter helpers would remove parallel truncation and JSON rendering paths.
- `MessageContainer.handle_event()` imports event classes inside method on each call; hoisting imports or using protocol methods could simplify and reduce runtime overhead.
- `_current_assistant` streaming lifecycle is manually reset on selected event classes; encapsulating this in a dedicated streaming state helper would reduce conditional branching.
