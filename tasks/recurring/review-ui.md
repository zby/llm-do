# Review: UI System

Periodic review of the UI system for bugs, inconsistencies, and improvements.

## Scope

- `llm_do/ui/` - Events, display backends, app
- `llm_do/ui/widgets/` - Message widgets, approval panel

## Checklist

- [ ] Event flow is clear and documented
- [ ] Display backends (headless, rich, TUI) behave consistently
- [ ] Streaming output works correctly
- [ ] Approval UI is functional and clear
- [ ] No dead code or unused CSS
- [ ] Error handling is appropriate

## Output

Record findings in `docs/notes/reviews/review-ui.md`.

## Last Run

2026-01 (streaming + truncation + literal rendering look consistent; remaining: minor rendering responsibility duplication)
