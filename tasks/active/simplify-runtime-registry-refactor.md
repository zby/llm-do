# Simplify runtime/registry refactor

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Refactor `runtime/registry.py` to remove duplicated parsing/merging logic while
preserving existing entry/override behavior.

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
    `build_worker_definition()`; parse a base `WorkerDefinition` once and only
    re-parse with overrides for the entry worker.
  - `_merge_toolsets()` currently allows duplicate names if the object is
    identical; call sites never rely on this, so consider always raising.
  - `entries` is built incrementally for conflict checks, then rebuilt; track
    `reserved_names` and build the final `entries` once at the end.
  - Overrides are intended to apply only to the entry worker.
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
  2. Expand `--set` to support targeting any worker (not just entry)
- Follow-ups: update tests for merge behavior changes and new override syntax

### `--set` Syntax Spec
New consistent syntax using colon separator:
```
--set model=gpt-4o              # entry worker (no colon = entry shorthand)
--set foo:model=gpt-4o          # worker named "foo"
--set worker:model=gpt-4o       # worker literally named "worker"
```
Rule: if there's a colon before the first `=`, the part before the colon is the
worker name. No colon means entry worker.

## Tasks
- [ ] Update `_merge_toolsets()` to always error on duplicate names (remove `is`
      identity check).
- [ ] Implement new `--set` syntax with colon separator for worker targeting:
      - Parse `<worker>:<field>=<value>` to target specific workers
      - Keep `<field>=<value>` as shorthand for entry worker
- [ ] Update `_build_registry_and_entry_name()` to apply overrides to targeted
      workers (not just entry).
- [ ] Parse `.worker` files once via `build_worker_definition(...)` for base
      validation; re-parse with overrides for workers that have them.
- [ ] Replace incremental `entries` building with a `reserved_names` set and
      build the final entries map once.
- [ ] Adjust tests to cover new override syntax and toolset merge conflicts.
- [ ] Run ruff, mypy, pytest.

## Current State
Quick cleanups applied in `llm_do/runtime/registry.py`; refactor work pending.

## Notes
- Expect minor error-message ordering shifts after refactor; keep tests resilient.
- Resolved questions:
  - Duplicate toolset names always error (even if same instance) — decided yes.
  - Overrides now support targeting any worker via `<worker>:<field>=<value>` syntax.
