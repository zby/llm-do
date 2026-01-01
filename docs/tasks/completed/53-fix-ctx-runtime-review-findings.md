# Fix: Ctx Runtime Review Findings

## Status
completed

## Prerequisites
- [x] none

## Goal
Fix the concrete correctness issues identified in `docs/notes/reviews/review-ctx-runtime.md` (and add regression tests) without changing the intended high-level runtime architecture.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/invocables.py:Worker.call` (spawns child ctx; chooses `message_history`)
  - `llm_do/ctx_runtime/ctx.py:CallFrame.fork` / `WorkerRuntime.spawn_child` (message history reset behavior)
  - `llm_do/ctx_runtime/cli.py:build_entry` (loads `.py` entries twice via discovery)
  - `llm_do/ctx_runtime/cli.py:_wrap_toolsets_with_approval` (rebuilds `Worker`; recurses)
  - `llm_do/ctx_runtime/discovery.py:load_module` (module naming + execution)
  - `llm_do/toolset_loader.py:build_toolsets` (mutates `_approval_config` on shared instances)
- Related tasks/notes/docs:
  - `docs/notes/reviews/review-ctx-runtime.md`
  - `docs/tasks/completed/41-review-ctx-runtime.md`
  - `docs/tasks/active/35-chat-support.md` (multi-turn message history intent)
- How to verify / reproduce:
  - Add regression tests and run `uv run pytest`.
  - (Bug repro) In `--tui --chat`, second-turn model behavior should differ when prior messages are provided; currently the top-level worker run does not receive prior history.

## Decision Record
- Decision:
  - Preserve prior message history for the top-level worker only; keep nested worker calls stateless by default.
  - Avoid double-importing Python files during `build_entry` by loading each module once per run, then discovering toolsets/workers from the same module object.
  - Approval wrapping preserves all `Worker` fields via `dataclasses.replace` and guards recursion with a visited-worker map.
- Inputs:
  - Review findings in `docs/notes/reviews/review-ctx-runtime.md`.
  - Existing “top-level-only” intent in `llm_do/ctx_runtime/invocables.py:_should_use_message_history`.
- Options:
  - Message history: copy parent `messages` into the spawned child ctx when `_should_use_message_history(child_ctx)`; or change `CallFrame.fork()` to optionally inherit messages.
  - Discovery: add caching to `load_module` keyed by resolved path; or add a new helper that loads modules once then runs both discover passes.
  - Approval wrapping: use `dataclasses.replace` for `Worker` to preserve fields; add recursion guard (visited set by object identity) for worker cycles.
- Outcome:
  - Implemented module single-load discovery, field-preserving approval wrapping, and cycle-safe recursion; added regression tests for each.
- Follow-ups:
  - If per-worker `_approval_config` for shared Python toolsets is required, document intended semantics (and likely introduce per-worker toolset instantiation/factories).

## Tasks
- [x] Add regression test: `message_history` is actually passed to the entry worker agent on turn 2 (chat flow).
- [x] Fix ctx runtime message-history propagation for the top-level worker (without enabling history for nested worker calls).
- [x] Add regression test: nested worker calls do not inherit caller message history.
- [x] Add regression test: `build_entry` executes each Python file only once (toolsets/workers discovered from same module instance).
- [x] Refactor discovery/build_entry to avoid double module execution (`load_toolsets_from_files` + `load_workers_from_files` duplication).
- [x] Add regression test: approval wrapping preserves `Worker` fields like `model_settings`.
- [x] Refactor approval wrapping to preserve all `Worker` fields (avoid hand-reconstruction).
- [x] Decide and implement cycle-safety for approval wrapping (guard recursion or validate worker graph).

## Current State
All review findings addressed with regression coverage: message history fixed for entry worker only, Python discovery loads modules once per run, and approval wrapping preserves fields while guarding cyclic worker graphs.

## Notes
- Keep scope to the ctx runtime; avoid UI or toolset changes unless needed for a regression test.
- If resolving `_approval_config` semantics requires design work, capture it in a note under `docs/notes/` instead of expanding this task.
