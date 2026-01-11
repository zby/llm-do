# Manifest-driven CLI (JSON)

## Status
ready for implementation

## Prerequisites
- [ ] confirm manifest filename / invocation shape in CLI help
- [ ] decide `--input-json` behavior (file path only vs inline JSON)
- [ ] align manifest schema defaults and validation rules

## Goal
Replace the discovery-based CLI path with a manifest-driven linker that loads a
JSON project file, resolves entries/toolsets/workers deterministically, and runs
the single manifest-defined entry. Manifest is authoritative for linking/runtime
config; CLI input overrides are gated by `allow_cli_input`.

## Context
- Relevant files/symbols:
  - `llm_do/cli/main.py` (CLI parsing + run flow)
  - `llm_do/runtime/registry.py` (entry linking utilities to replace/relocate)
  - `llm_do/runtime/discovery.py` (module discovery)
  - `llm_do/runtime/worker.py` (EntryFunction, WorkerToolset)
  - `llm_do/runtime/shared.py` (Runtime.run_entry, run_invocable)
  - `docs/notes/manifest-driven-cli-plan.md` (design spec)
- Related tasks/notes/docs:
  - `tasks/active/212-simplify-entry-registry.md`
  - `docs/notes/manifest-driven-cli-plan.md`
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: CLI invocation shape is `llm-do project.json [prompt]`.
- Inputs: CLI should link a single manifest-defined entry.
- Options: `llm-do run project.json` vs positional manifest.
- Outcome: positional manifest path + optional prompt.
- Follow-ups: confirm `llm-do.json` default behavior in help/usage.

## Tasks
- [ ] Add manifest loader + schema validation (JSON).
- [ ] Resolve toolsets/workers/entries per manifest-driven linker flow.
- [ ] Add `allow_cli_input` gating and `--input-json` support.
- [ ] Remove CLI flags superseded by the manifest (entry/model/set/approval/max-depth/files).
- [ ] Update CLI help/docs/tests to reflect new interface.
- [ ] Update any example scripts or docs to use manifest format.
- [ ] Run lint, typecheck, tests.

## Current State
Task created; manifest-driven CLI not implemented yet.

## Notes
- Manifest `toolsets` can reference built-ins and Python toolset names.
- Name collisions between workers/toolsets/entries must raise errors.
- `runtime` config is required in the manifest.
