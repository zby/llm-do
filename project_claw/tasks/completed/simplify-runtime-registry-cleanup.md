# Simplify runtime registry cleanup

## Status
completed

## Prerequisites
- [x] none

## Goal
Apply the simplifications noted in `docs/notes/reviews/simplify-runtime-registry.md` to reduce redundant maps/checks and align the registry flow.

## Context
- Relevant files/symbols: `llm_do/runtime/registry.py`, `llm_do/runtime/discovery.py`, `llm_do/toolsets/loader.py`
- Related tasks/notes/docs: `docs/notes/reviews/simplify-runtime-registry.md`
- How to verify / reproduce: run registry build paths used by CLI; ensure entry/toolset resolution is unchanged.

## Decision Record
- Decision: Introduced WorkerSpec dataclass and simplified the two-pass flow
- Inputs: Review notes in simplify-runtime-registry.md
- Options: Keep separate dicts vs consolidate into WorkerSpec
- Outcome: Consolidated into WorkerSpec, removed redundant workers dict, lazy global toolset map
- Follow-ups: None

## Tasks
- [x] Remove redundant conflict check when inserting Python entries (already enforced in discovery).
- [x] Drop the extra `workers` mapping and update `entries` from `worker_entries` directly.
- [x] Avoid reassigning stub fields that are already set, or switch to minimal stub assignment then single fill.
- [x] Consolidate per-worker bookkeeping (consider a small struct to hold name/path/definition/stub).
- [x] Build the global toolset map only when needed for entry function toolset refs.
- [x] Update tests or docs if behavior changes; verify no functional changes beyond simplification.

## Current State
All simplifications applied. All 177 runtime tests pass.

## Notes
- Changes are cosmetic; preserve behavior while reducing duplicated data flow.
- Added WorkerSpec dataclass to consolidate worker_entries, worker_paths, worker_defs into single structure
- Stubs now created with minimal fields, filled in second pass (avoiding duplicate assignments)
- Global toolset map only built when entry functions have toolset_refs
