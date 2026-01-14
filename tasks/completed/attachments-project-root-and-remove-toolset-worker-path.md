# Normalize Attachment Paths; Remove Toolset worker_path

## Status
completed

## Prerequisites
- [ ] none

## Goal
Attachments resolve relative to a single project root for all workers, and the unused `ToolsetBuildContext.worker_path`/`worker_dir` is removed (docs/examples/tests updated accordingly).

## Context
- Relevant files/symbols:
  - `llm_do/runtime/worker.py` (`_resolve_attachment_path`, attachment handling, `Worker.base_path`)
  - `llm_do/runtime/shared.py` (`RuntimeConfig` for project root config)
  - `llm_do/cli/main.py` (set project root from manifest dir)
  - `llm_do/runtime/registry.py` (currently passes `worker_path` into `ToolsetBuildContext`)
  - `llm_do/toolsets/loader.py` (`ToolsetBuildContext.worker_path`, `worker_dir`)
  - `llm_do/runtime/schema_refs.py` (schema base path remains separate; do not change)
  - Docs/examples using `Worker.base_path`: `examples/pitchdeck_eval_direct/run.py`, `examples/pitchdeck_eval_direct/README.md`, `docs/notes/reviews/useless-features-audit.md`
- Related tasks/notes/docs:
  - `docs/notes/unified-entry-function-design.md` (tool plane vs raw Python, parity)
  - `docs/notes/archive/base-path-working-directory-design.md` (historical context; do not edit)
- How to verify / reproduce:
  - Add/adjust a unit test so a relative attachment path resolves against project root, not CWD or worker-specific paths.
  - Run `uv run pytest`.

## Decision Record
- Decision: Resolve attachment paths relative to a single project root for all workers; remove `ToolsetBuildContext.worker_path`/`worker_dir` and any wiring for it.
- Inputs: current behavior uses per-worker `base_path` (or CWD), which causes inconsistent attachment resolution; `worker_path` is unused by built-in toolsets.
- Options:
  - Keep per-worker base_path (current behavior) and document it.
  - Use worker file directory for attachments.
  - Use a runtime-wide project root for all attachments; remove per-worker base path.
- Outcome: Use runtime-wide project root (CLI: manifest dir; scripts: explicit or default), remove toolset `worker_path` context.
- Follow-ups:
  - Decide whether to remove `Worker.base_path` entirely or keep only for non-attachment use (if any).
  - Update docs/examples that reference `Worker.base_path` for attachments.

## Tasks
- [x] Add `project_root` to `RuntimeConfig` and plumb it into `Runtime` construction (CLI uses manifest dir; script callers can pass explicitly).
- [x] Update attachment resolution to use runtime `project_root` (fallback to CWD if unset); remove per-worker `base_path` usage.
- [x] Remove `ToolsetBuildContext.worker_path`/`worker_dir` and all wiring in registry/builders.
- [x] Update docs/examples/tests that set `Worker.base_path` for attachments to use project root instead.
- [x] Add/adjust tests for attachment path resolution and any registry/toolset context removal.

## Current State
Implementation complete. All 330 tests pass.

### Changes Made:
1. Added `project_root: Path | None` to `RuntimeConfig` and `Runtime` in `llm_do/runtime/shared.py`
2. Added `project_root` property to `WorkerRuntime` in `llm_do/runtime/deps.py`
3. Updated attachment resolution in `Worker._call_internal()` to use `project_root` from runtime (fallback to CWD)
4. CLI passes `manifest_dir` as `project_root` to Runtime in `llm_do/cli/main.py`
5. Added `project_root` parameter to `run_tui()`, `run_headless()`, `run_ui()` in `llm_do/ui/runner.py`
6. Removed `worker_path` field and `worker_dir` property from `ToolsetBuildContext` in `llm_do/toolsets/loader.py`
7. Removed `worker_path` wiring from registry in `llm_do/runtime/registry.py` (2 locations)
8. Removed `worker_path` from fallback `ToolsetBuildContext` in `Worker._resolve_toolset_context()`
9. Updated `examples/pitchdeck_eval_direct/run.py` to pass `project_root` to `run_ui()` and removed `base_path`
10. Updated `examples/pitchdeck_eval_direct/README.md` to show new pattern
11. Updated `docs/notes/reviews/useless-features-audit.md` to mark `base_path` as removed
12. Added `tests/runtime/test_attachment_path.py` with unit tests for path resolution and project_root
13. Removed `Worker.base_path` field entirely (no longer used)
14. Removed `base_path` from experiment files

### Notes:
- `Worker.base_path` was removed entirely since it's no longer used
- Existing tests didn't use `worker_path` parameter, so no test changes needed

## Notes
- Built-in toolsets use `filesystem_project` derived from worker dir today; consider whether that should align with project root later (not required for this task).
