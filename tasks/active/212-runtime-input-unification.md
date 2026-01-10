# Runtime Input Unification

## Status
ready for implementation

## Prerequisites
- [ ] design decision needed (canonical input object + args model contract)

## Goal
Define and implement a single canonical runtime input model so worker prompt
construction and tool-facing prompt access cannot drift.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/shared.py` (`Runtime.run_invocable`)
  - `llm_do/runtime/deps.py` (`WorkerRuntime.run`, `CallFrame.prompt`, `RunContext.prompt`)
  - `llm_do/runtime/worker.py` (`_build_user_prompt`, `Worker.call`)
- Related tasks/notes/docs:
  - `docs/notes/reviews/simplify-runtime-runner.md` (prompt duplication analysis)
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Use a canonical args model base class (`WorkerArgs`) that defines `prompt_spec()`; runtime is strict about worker calls receiving args models. Derive prompt text from `prompt_spec().text` (Option 1 semantics).
- Inputs: Prompt/input drift between `input_data` and `ctx.prompt`; tools only see string prompts; attachments are handled separately in task 213.
- Options: (1) Canonical structured input + derived prompt string (chosen). (2) Canonical rendered prompt content. (3) Deprecate prompt and require explicit accessors. (4) Implicit input coercion (rejected; strict args model required).
- Outcome: `RunContext.prompt` is for logging/UI only and is derived from args. Tools should not rely on it and should operate purely on tool args. `ctx.deps` is for worker delegation only (soft policy, documented). Worker inputs must be subclasses of `WorkerArgs`.
- Follow-ups: Coordinate with `tasks/active/213-attachment-approval-gating.md` for attachment handling via approvals.

## Tasks
- [ ] Document current prompt/input flow and failure modes (ctx.prompt drift)
- [x] Decide canonical input object + tool-facing prompt semantics
- [x] Decide strict args model contract (`WorkerArgs` + `prompt_spec()`)
- [ ] Specify API changes (WorkerArgs base class, PromptSpec type, RunContext.prompt behavior)
- [ ] Update worker input handling to require args models (no implicit coercion)
- [ ] Document soft policy: tools should use args only; `ctx.deps` is for worker delegation (docs + code comments)
- [ ] Implement + update tests/docs/examples

## Current State
Decision made: canonical args model base class with `prompt_spec()`; strict worker call inputs.
Implementation plan is defined; no code changes applied yet.

## Notes
- Today `input_data` (structured) and `ctx.prompt` (string) can diverge, and
  tools only see the string even when the LLM prompt is multimodal.
