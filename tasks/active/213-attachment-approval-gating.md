# Attachment Approval Gating

## Status
information gathering

## Prerequisites
- [ ] design decision needed (attachment reads via approved tool calls)

## Goal
Ensure worker attachments are resolved through the approval system by routing
file reads through an approved tool call rather than direct filesystem access.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/worker.py` (`_build_user_prompt`, `_load_attachment`)
  - `llm_do/runtime/deps.py` (`WorkerRuntime.call`, tool invocation)
  - `llm_do/toolsets/filesystem.py` (candidate toolset for attachment reads)
  - `llm_do/runtime/approval.py` (approval wrapping + policy)
- Related tasks/notes/docs:
  - `tasks/active/212-runtime-input-unification.md`
  - `docs/notes/reviews/simplify-runtime-runner.md` (prompt/approval gaps)
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision:
- Inputs:
- Options:
- Outcome:
- Follow-ups:

## Tasks
- [ ] Decide attachment toolset strategy (FilesystemToolset vs dedicated AttachmentToolset)
- [ ] Decide when attachments are resolved (pre-prompt async step, per-call)
- [ ] Define approval/UI behavior (per-file prompts, caching, error handling)
- [ ] Implement attachment resolution via approved tool calls
- [ ] Update tests/docs and examples

## Current State
New task. Attachment reads currently bypass approval and need a policy decision
before implementation.

## Notes
- `_load_attachment` performs direct file reads today; tool approvals only cover
  LLM-invoked tools, not prompt-time filesystem access.
