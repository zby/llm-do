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

## 2026-02-09 Review
- `_consume_events()` performs repeated widget lookups and mixed responsibilities (queue loop, rendering delegation, app state transitions). Splitting queue consumption from state transitions would simplify.
- Approval input-disable/enable logic is spread across `_enqueue_approval_request`, `_resolve_approval`, and completion/error branches; centralizing input-state transitions would reduce drift.
- `_messages` stores completed text responses only for final output; if final output can be derived from message history, this extra accumulator can be removed.
