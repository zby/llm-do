# Simplify runtime/registry refactor

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Refactor `runtime/registry.py` to remove duplicated parsing/merging logic,
tighten toolset merge rules, and remove override handling entirely until it is
reintroduced later via a dedicated task.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/registry.py` - entry linking, toolset merging, worker parsing
  - `llm_do/runtime/worker_file.py` - worker frontmatter parsing/validation
  - `llm_do/runtime/discovery.py` - python toolset/worker/entry discovery
  - `llm_do/toolsets/loader.py` - toolset resolution and instantiation
- Related tasks/notes/docs:
  - `docs/notes/reviews/simplify-runtime-registry.md`
- Inline review findings (from `docs/notes/reviews/simplify-runtime-registry.md`):
  - `_worker_toolset_spec()` duplicates `Worker.as_toolset_spec()`; build
    `available_workers` via `spec.stub.as_toolset_spec()` and delete helper.
  - `EntryFunction.toolset_context` is assigned twice; `resolve_toolsets()`
    already sets it.
  - Entry/name validation is duplicated between registry and
    `build_worker_definition()`; parse a base `WorkerDefinition` once and
    re-parse with overrides only for workers that have them.
  - `_merge_toolsets()` currently allows duplicate names if the object is
    identical; call sites never rely on this, so consider always raising.
  - `entries` is built incrementally for conflict checks, then rebuilt; track
    `reserved_names` and build the final `entries` once at the end.
  - (Old behavior) Overrides applied only to the entry worker — now removed
    entirely since `--set` is not exposed in the CLI.
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: made
- Inputs: registry simplification review findings
- Options: keep behavior as-is vs. tighten toolset merge rules
- Outcome:
  1. Always error on duplicate toolset names (remove `is` identity check)
  2. Remove override plumbing (`--set`, worker overrides) from the runtime
     implementation and tests until it is reintroduced in a dedicated task
- Follow-ups: update tests for merge behavior changes; add backlog task for overrides

### `--set` Syntax Spec
Deprecated: override syntax removed for now. See backlog task for reintroduction.

## Tasks
- [x] Remove override plumbing from worker parsing/registry (delete config
      override helpers and any `set_overrides` parameters).
- [x] Update `_merge_toolsets()` to always error on duplicate names (remove `is`
      identity check).
- [x] Parse `.worker` files once via `build_worker_definition(...)` for base
      validation (no overrides).
- [x] Replace incremental `entries` building with a `reserved_names` set and
      build the final entries map once.
- [x] Remove override-related tests; add/adjust tests for merge conflicts.
- [ ] Run ruff, mypy, pytest.

## Current State
Override support removed (config helpers + `set_overrides` plumbing), registry
refactor applied (reserved names, single parse, strict toolset merge), and
tests updated to drop override coverage and cover toolset name conflicts.

## Notes
- Expect minor error-message ordering shifts after refactor; keep tests resilient.
- Resolved questions:
  - Duplicate toolset names always error (even if same instance) — decided yes.
  - Overrides are removed entirely; reintroduce later via a backlog task.
