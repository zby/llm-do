# Per-Call Toolset Instances

## Status
completed

## Prerequisites
- [ ] none

## Goal
Per-call toolset instances with deterministic cleanup, using a single specs-based path and no shared-instance behavior.

## Motivation
Toolsets are currently instantiated per entry build, not per call, which breaks isolation for recursive or nested worker calls.
If Worker A calls itself, both invocations share the same toolset objects, so state and handles leak across calls and cleanup runs only once.
That makes debugging unpredictable and can corrupt stateful toolsets.

Example failure mode:
```
Worker A (call 1)
  └── Worker A (call 2)  ← shares toolset instances from call 1
```

## Context
- Relevant files/symbols: `llm_do/runtime/worker.py`, `llm_do/runtime/shared.py`, `llm_do/runtime/registry.py`, `llm_do/toolsets/loader.py`
- Related tasks/notes/docs: `tasks/completed/113-per-worker-toolset-instances.md`, `docs/notes/reviews/review-solid.md`
- How to verify / reproduce: add/extend tests to show recursive worker calls get isolated toolset instances; run `uv run pytest`

## Decision Record
- Decision: use a single path based on toolset specs; remove shared `toolsets` instances
- Inputs: per-call isolation required; shared instances leak state; repo guidance says no backcompat
- Options: keep dual fields (rejected); only specs with migration (chosen)
- Outcome: worker definitions and registry populate `toolset_specs` only; `Worker` instantiates per-call and cleans up in `Worker._call_internal`; entry-level cleanup removed
- Follow-ups: update any docs or examples that reference `toolsets`

## Tasks
- [x] Remove `toolsets` field from `Worker` and add `toolset_specs: list[ToolsetSpec]`
- [x] Update `Worker._call_internal` to instantiate from specs per call
- [x] Add cleanup in `Worker._call_internal` finally block (extract helper from Runtime as needed)
- [x] Remove cleanup from `Runtime.run_entry()` (no entry-level instantiation remains)
- [x] Update registry to populate `toolset_specs` for worker files
- [x] Update toolset loader to produce specs-only data
- [x] Update docs/examples that reference `toolsets` to use `toolset_specs`
- [x] Update tests to verify per-call isolation
- [x] Add test for recursive worker with stateful toolset

## Current State
Implemented per-call toolset spec resolution and instantiation, updated docs/examples/tests, and verified with ruff, mypy, and pytest.

## Notes
- Migration: update any worker definitions or registry outputs that previously passed `toolsets` to use specs instead.
