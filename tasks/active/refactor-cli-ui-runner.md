# Refactor CLI to Use UI Runner API

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
CLI uses expanded `run_tui` / `run_headless` from `llm_do/ui/runner.py` for UI execution so the CLI no longer duplicates TUI/headless orchestration while preserving CLI-specific behavior (chat mode, log verbosity, JSON output, message logging, and error handling).

## Context
- Relevant files/symbols:
  - `llm_do/cli/main.py` (`_run_tui_mode`, `_run_headless_mode`, `run`)
  - `llm_do/ui/runner.py` (`run_tui`, `run_headless`, `run_ui`)
  - `llm_do/ui/app.py` (`LlmDoApp`, chat flow)
  - `llm_do/ui/display.py` (headless/JSON backends)
  - `llm_do/runtime/approval.py` (`RunApprovalPolicy`)
- Related tasks/notes/docs:
  - `docs/notes/reviews/review-ui.md` (rendering responsibilities, streaming handling)
- How to verify / reproduce:
  - `uv run pytest`
  - Manual smoke: `llm-do project.json --tui`, `llm-do project.json --headless`, `llm-do project.json --json`

## Decision Record
- Decision: Expand `run_tui` / `run_headless` API (Option A) and refactor CLI to call them.
- Inputs: CLI and example both implement similar TUI/headless orchestration; `run_ui` exists but CLI doesn’t use it.
- Options:
  - Expand `run_tui` / `run_headless` to cover CLI needs (chosen).
  - Add lower-level `run_*_app` helper and keep current `run_ui`.
- Outcome: Proceed with expanded runner API; keep CLI-specific entry/manifest concerns in CLI, but use shared runners for UI orchestration.
- Decision: Headless runs must reject `approval_mode="prompt"` for both the CLI and Python runner entrypoints (fail fast).
- Inputs: `run_headless` already rejects prompt; CLI headless currently falls back to deny-by-default.
- Outcome: Align CLI with runner behavior by validating upfront; no CLI doc changes required.

## Tasks
- [ ] Inventory CLI-only behavior to preserve (chat mode, log verbosity, JSON output, message log callback, error handling paths).
- [ ] Expand `run_tui` / `run_headless` signatures to accept:
  - `run_turn` callback + message history plumbing for chat
  - Additional display backends (log backend / JSON backend)
  - Optional `message_log_callback` or runtime override hooks
  - Error handling + verbosity parity with CLI
- [ ] Refactor `llm_do/cli/main.py` to call expanded runners and remove duplicated orchestration.
- [ ] Update any relevant docs/examples (CLI help text, UI runner usage).
- [ ] Run `uv run ruff check .`, `uv run mypy llm_do`, `uv run pytest`.

## Current State
Task created; runner expansion chosen; headless prompt rejection decision recorded. No implementation changes yet.

## Notes
- None.
