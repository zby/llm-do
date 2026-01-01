# Fix: Ctx Runtime Review Findings

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Fix the concrete correctness issues identified in `docs/notes/reviews/review-ctx-runtime.md` (and add regression tests) without changing the intended high-level runtime architecture.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/invocables.py:WorkerInvocable.call` (spawns child ctx; chooses `message_history`)
  - `llm_do/ctx_runtime/ctx.py:CallFrame.fork` / `WorkerRuntime.spawn_child` (message history reset behavior)
  - `llm_do/ctx_runtime/cli.py:build_entry` (loads `.py` entries twice via discovery)
  - `llm_do/ctx_runtime/cli.py:_wrap_toolsets_with_approval` (rebuilds `WorkerInvocable`; recurses)
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
  - Avoid double-importing Python files during `build_entry` (load each module once per run and then discover toolsets/workers from the same module object).
  - Approval wrapping should preserve all `WorkerInvocable` fields and be cycle-safe (either detect and stop recursion, or disallow cycles with a clear error).
- Inputs:
  - Review findings in `docs/notes/reviews/review-ctx-runtime.md`.
  - Existing “top-level-only” intent in `llm_do/ctx_runtime/invocables.py:_should_use_message_history`.
- Options:
  - Message history: copy parent `messages` into the spawned child ctx when `_should_use_message_history(child_ctx)`; or change `CallFrame.fork()` to optionally inherit messages.
  - Discovery: add caching to `load_module` keyed by resolved path; or add a new helper that loads modules once then runs both discover passes.
  - Approval wrapping: use `dataclasses.replace` for `WorkerInvocable` to preserve fields; add recursion guard (visited set by object identity) for worker cycles.
- Outcome:
  - TBD (implement and update).
- Follow-ups:
  - If per-worker `_approval_config` for shared Python toolsets is required, document intended semantics (and likely introduce per-worker toolset instantiation/factories).

## Tasks
- [x] Add regression test: `message_history` is actually passed to the entry worker agent on turn 2 (chat flow).
- [x] Fix ctx runtime message-history propagation for the top-level worker (without enabling history for nested worker calls).
- [x] Add regression test: nested worker calls do not inherit caller message history.
- [ ] Add regression test: `build_entry` executes each Python file only once (toolsets/workers discovered from same module instance).
- [ ] Refactor discovery/build_entry to avoid double module execution (`load_toolsets_from_files` + `load_workers_from_files` duplication).
- [ ] Add regression test: approval wrapping preserves `WorkerInvocable` fields like `model_settings`.
- [ ] Refactor approval wrapping to preserve all `WorkerInvocable` fields (avoid hand-reconstruction).
- [ ] Decide and implement cycle-safety for approval wrapping (guard recursion or validate worker graph).

## Current State
Message history now works as intended for chat:
- Entry worker receives `message_history` on turn 2+.
- Nested worker calls remain stateless (do not inherit the caller's conversation).

Remaining work: Python discovery double-load + approval wrapping field preservation/cycle safety.

## Notes
- Keep scope to the ctx runtime; avoid UI or toolset changes unless needed for a regression test.
- If resolving `_approval_config` semantics requires design work, capture it in a note under `docs/notes/` instead of expanding this task.
