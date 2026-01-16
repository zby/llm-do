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
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: pending
- Inputs: registry simplification review findings
- Options: keep behavior as-is vs. tighten toolset merge rules
- Outcome: TBD
- Follow-ups: update tests for override and merge behavior changes

## Tasks
- [ ] Parse `.worker` files once via `build_worker_definition(...)` for base
      validation; re-parse only the entry worker with `overrides` applied.
- [ ] Replace incremental `entries` building with a `reserved_names` set and
      build the final entries map once.
- [ ] Decide on `_merge_toolsets()` duplicate-key policy; update error messaging.
- [ ] Adjust tests to cover entry override parsing and toolset merge conflicts.
- [ ] Run ruff, mypy, pytest.

## Current State
Quick cleanups applied in `llm_do/runtime/registry.py`; refactor work pending.

## Notes
- Entry overrides must continue to apply only to the entry worker.
- Expect minor error-message ordering shifts after refactor; keep tests resilient.
