# Simplify: ui/runner.py

## Context
Review of TUI/headless run orchestration helpers.

## Findings
- `run_tui()` and `run_headless()` share substantial logic (runtime creation,
  event adaptation, render loop wiring). Extract common pieces to reduce
  parallel code paths. Done: render loop + event adaptation now shared via
  `_start_render_loop`; remaining duplication is in run flow and error
  handling.
- `run_tui()` nests many small helpers (`emit_error`, `run_entry`,
  `run_with_input`, `run_turn`). Pulling these into a small helper class or
  module-level functions would simplify control flow.
- Queue/render-task shutdown logic is duplicated between normal and error
  paths. A small context manager for render loop lifecycle could simplify.

## Open Questions
- Should `run_ui()` be the primary entry, with mode-specific wrappers thinly
  delegating to shared helpers?
