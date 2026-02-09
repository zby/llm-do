# Simplify: ui/controllers/

## Context
Review of controller helpers (`agent_runner.py`, `approval_workflow.py`,
`exit_confirmation.py`, `input_history.py`).

## Findings
- `AgentRunner.start_background()` and `start_turn_task()` are near duplicates
  (both create a task and set `_task`). A single helper could reduce
  duplication and keep error handling consistent.
- `ApprovalWorkflowController` tracks `_batch_total` and `_batch_index` in
  parallel with the queue length. If the batch semantics are simple, consider
  deriving these from queue state to reduce internal state.
- `ExitConfirmationController` is small and could be folded into `LlmDoApp`
  if no other users exist, reducing file count.

## 2026-02-09 Review
- Controllers remain small and focused; the largest simplification opportunity is consolidating repeated `is_running`/task-start checks in `AgentRunner` into one private helper.
- `ApprovalWorkflowController` keeps both `_batch_total` and `_batch_index`; numbering can likely be derived from queue state plus consumed count without dual mutable counters.
