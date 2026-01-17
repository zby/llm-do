# Review: UI System

Periodic review of the UI system for bugs, inconsistencies, and improvements.

## Scope

- `llm_do/ui/app.py` - Main TUI application
- `llm_do/ui/runner.py` - UI runner orchestration
- `llm_do/ui/events.py` - UI event types
- `llm_do/ui/display.py` - Display backends
- `llm_do/ui/adapter.py` - Runtime-to-UI adapter
- `llm_do/ui/formatting.py` - Output formatting
- `llm_do/ui/parser.py` - Input parsing
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
