# Attachment Approval Gating

## Status
completed

## Prerequisites
- [x] none

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
- Decision: Use a dedicated AttachmentToolset with pre-prompt resolution.
- Inputs: Attachment reads bypass approval; need gating without model-driven access.
- Options:
  - Dedicated AttachmentToolset vs FilesystemToolset
  - Pre-prompt resolution vs lazy tool call
  - Per-file prompts vs batch approvals; fail fast vs placeholder
- Outcome: Dedicated AttachmentToolset; pre-prompt resolution; per-file prompts; session caching by absolute path; fail fast on denial.
- Follow-ups: Implement toolset + pre-prompt gating; update tests/docs as needed.

## Tasks
- [x] Decide attachment toolset strategy (FilesystemToolset vs dedicated AttachmentToolset)
- [x] Decide when attachments are resolved (pre-prompt async step, per-call)
- [x] Define approval/UI behavior (per-file prompts, caching, error handling)
- [x] Implement attachment resolution via approved tool calls
- [x] Update tests/docs and examples

## Current State
Implementation complete with AttachmentToolset + pre-prompt approval gating; tests updated.

## Notes
- Attachment reads now flow through AttachmentToolset with approval gating.
