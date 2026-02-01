# Simplify: ui/app.py

## Context
Review of the Textual TUI app orchestration code.

## Findings
- Approval UI logic is split across `_enqueue_approval_request()`,
  `_render_active_approval()`, and `_resolve_approval()`. A single controller
  method that returns "input enabled" state could simplify the branching.
- `action_approve()`, `action_approve_session()`, and `action_deny()` are thin
  wrappers around `_resolve_approval()`; consider a small dispatch helper to
  reduce repetitive action methods.
- `_consume_events()` handles both rendering and state transitions; moving
  "done" handling and error handling into `MessageContainer` or a dedicated
  controller would simplify the loop.

## Open Questions
- Should the app own approval queue state, or can that live entirely in the
  `ApprovalWorkflowController`?
