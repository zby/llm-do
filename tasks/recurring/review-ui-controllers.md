# Review: UI Controllers

Periodic review of UI controller components for bugs, inconsistencies, and improvements.

## Scope

- `llm_do/ui/controllers/approval_workflow.py` - Approval flow management
- `llm_do/ui/controllers/worker_runner.py` - Worker execution coordination
- `llm_do/ui/controllers/input_history.py` - Input history tracking
- `llm_do/ui/controllers/exit_confirmation.py` - Exit confirmation handling

## Checklist

- [ ] Controller responsibilities are clear and non-overlapping
- [ ] State management is consistent
- [ ] Event handling follows established patterns
- [ ] Error states are handled gracefully
- [ ] Controllers don't duplicate logic from ui/app.py or ui/runner.py
- [ ] Async coordination is correct

## Output

Record findings in `docs/notes/reviews/review-ui-controllers.md`.

