# Explicit Entry Marker + Single Entry Resolution

## Status
completed

## Prerequisites
- [ ] none

## Goal
Adopt explicit entry marking for worker files and enforce a single entry candidate per build, with hard errors on duplicate `@entry` functions or worker entry conflicts.

## Context
- Why now:
  - Single-entry runs are the norm; registry is an internal linker detail.
  - We want deterministic entry selection without manifest-based entry switching.
- Relevant files/symbols:
  - `llm_do/runtime/worker_file.py` (frontmatter parsing, WorkerDefinition)
  - `llm_do/runtime/registry.py` (entry/linking, selection logic)
  - `llm_do/runtime/worker.py` (`@entry` decorator, EntryFunction)
  - `llm_do/runtime/manifest.py` (entry selection fields)
  - `llm_do/cli/main.py` (CLI selection flow)
  - `docs/notes/archive/hide-entry-registry.md` (design note)
  - `docs/architecture.md`, `docs/reference.md`, `docs/cli.md` (docs updates)
  - `tests/runtime/test_build_entry_resolution.py` (entry resolution tests)
- Related tasks/notes/docs:
- `docs/notes/archive/hide-entry-registry.md`
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Use explicit worker frontmatter marking (e.g., `entry: true`) for entry selection; allow at most one `@entry` function; error on duplicates or conflicts.
- Inputs: Single-entry model; avoid manifest-based entry switching; make entry selection deterministic and explicit.
- Options: explicit marker vs naming convention vs hybrid; allow multiple `@entry` functions.
- Outcome: explicit marker + single-entry rule.
- Follow-ups: confirm manifest/CLI entry selection removal and update docs accordingly.

## Summary of Existing Architecture (for self-contained context)
- `build_entry_registry()` performs the linker step:
  - Loads toolsets/workers/`@entry` functions from python files.
  - Loads worker definitions, creates stubs, resolves toolset names.
  - Applies schema refs and model overrides.
- The registry is a symbol table; removing it publicly does not remove the link step.
- `Runtime.run_entry()` currently runs an entry by name from the registry.

## API Sketch
- New/updated builder:
  - `build_entry(worker_files, python_files, *, entry_model_override=None, set_overrides=None) -> Entry`
  - Internally calls the existing linker (`build_entry_registry`) and returns the single resolved entry.
- Runtime execution:
  - Use `Runtime.run_invocable(entry, input_data)` everywhere.
  - Remove or de-emphasize `Runtime.run_entry()` / `run_entry_sync()` (internal only if kept).
- Worker frontmatter:
  - Add `entry: true` boolean (explicit marker).
  - Validation: allow at most one marked worker per build unit.

## Entry Selection Rules
- Discover `@entry` functions from python files:
  - If count > 1, error and list candidates.
- Discover worker entries (frontmatter `entry: true`):
  - If count > 1, error and list candidates.
- If both a `@entry` function and a marked worker exist, error.
- If none exist, error ("no entry found").
- If exactly one candidate exists, return it.

## Runtime.run_entry Usage Catalog
- `llm_do/cli/main.py` (primary runtime invocation)
- `tests/runtime/test_cli_approval_session.py` (2 calls)
- `tests/runtime/test_events.py` (2 calls)
- `docs/architecture.md` (mentions run_entry in flow)
- `docs/reference.md` (API reference for run_entry)
- `llm_do/runtime/shared.py` (definition only)

## Runtime.run_entry_sync Assessment
- Current usage: none found outside `llm_do/runtime/shared.py` definition.
- `Runtime.run()` already provides sync execution for an `Entry`.
- Decision: remove `run_entry_sync()` entirely; update call sites/docs to use
  `Runtime.run_invocable()` or `Runtime.run()`.

## Error Cases to Test
- Two `.worker` files marked `entry: true` → hard error.
- Two `@entry` functions in same file set → hard error.
- One marked worker + one `@entry` function → hard error.
- No marked worker and no `@entry` function → hard error.

## Benefits
- Smaller public surface: build + run against a single `Entry`.
- Clearer mental model: "link to one entry, then execute".
- Avoids manifest-based entry switching that isn't needed.

## Costs / Risks
- Code removal is modest; linker still exists.
- Entry switching requires changing file set or entry marker.
- Must preserve good error messages (list candidates) without exposing registry.
- Toolset resolution remains global by name; build still loads all toolsets.

## Variants (if needed)
- Explicit marker only (this task).
- Convention only (e.g., `main.worker`) to avoid new schema fields.
- Hybrid (marker wins, else convention).
- Entry bundle return type (`(entry, metadata)`) for better diagnostics.

## Tasks
- [x] Add `entry` boolean to `WorkerDefinition` and parse/validate it in `llm_do/runtime/worker_file.py`.
- [x] Implement single-entry selection and conflict checks during linking (new `build_entry(...)` or within registry build).
- [x] Enforce `@entry` uniqueness and conflict rules (error on >1, or when both entry worker and `@entry` exist).
- [x] Update CLI/manifest to stop selecting entry by name and rely on explicit marking.
- [x] Update docs to describe explicit entry marking and single-entry resolution.
- [x] Add tests for duplicate markers, duplicate `@entry` functions, and worker/function conflicts.
- [x] Remove `Runtime.run_entry()` / `run_entry_sync()` and update call sites/docs to use `run_invocable()` or `run()`.

## Current State
Explicit entry markers and single-entry resolution implemented; CLI/manifest/docs/tests updated. `build_entry_registry` is now internal-only (not re-exported).

## Notes
- Explicit marking is preferred over naming conventions for now.
- Align docs and examples with `entry: true` usage.
