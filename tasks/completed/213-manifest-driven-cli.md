# Manifest-driven CLI (JSON)

## Status
completed

## Prerequisites
- [x] confirm manifest filename / invocation shape in CLI help
- [x] decide `--input-json` behavior (file path only vs inline JSON)
- [x] align manifest schema defaults and validation rules

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
- Related tasks/notes/docs:
  - `tasks/completed/212-simplify-entry-registry.md`
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: CLI invocation shape is `llm-do project.json [prompt]`.
- Inputs: CLI should link a single manifest-defined entry.
- Options: `llm-do run project.json` vs positional manifest.
- Outcome: positional manifest path + optional prompt.
- Decision: manifest path is required; no implicit `llm-do.json` default.
- Decision: manifest must contain exactly one entry (single object, not a map).
- Decision: when `allow_cli_input` is false, any CLI overrides (prompt/`--input-json`) are errors.
- Decision: `allow_cli_input` defaults to true; CLI input overrides `entry.input`.
- Decision: manifest schema uses Pydantic models (strict: `extra="forbid"`), with a required `version` field.
- Decision: locate manifest models in runtime (`llm_do/runtime/manifest.py`) so CLI and runtime share validation.
- Decision: `--input-json` accepts inline JSON only (no file paths).
- Decision: `runtime` fields default to approval_mode=prompt, max_depth=5, return_permission_errors=false.
- Decision: file paths resolve relative to the manifest directory.

## Manifest Schema (v1)
- Strict JSON only; Pydantic models use `extra="forbid"`.
- `version`: required int, must be `1`.
- `runtime`: required object.
  - `approval_mode`: `"prompt" | "approve_all" | "reject_all"` (default `"prompt"`).
  - `max_depth`: int >= 1 (default `5`).
  - `model`: optional string (global default model).
  - `return_permission_errors`: bool (default `false`).
- `allow_cli_input`: bool (default `true`).
- `entry`: required object.
  - `name`: required non-empty string.
  - `model`: optional string (entry-specific override).
  - `input`: optional object used when CLI input is absent.
- `worker_files`: list of `.worker` file paths (default `[]`).
- `python_files`: list of `.py` file paths (default `[]`).
- File list entries must be non-empty strings; duplicates are errors.
- Paths resolve relative to the manifest file's directory.
- CLI input overrides `entry.input` only when `allow_cli_input` is true; otherwise prompt/`--input-json` are errors.
- `--input-json` accepts inline JSON only (no file paths).

Example:

```json
{
  "version": 1,
  "runtime": {"approval_mode": "prompt", "max_depth": 5},
  "allow_cli_input": true,
  "entry": {"name": "main", "input": {"input": "Hello"}},
  "worker_files": ["workers/main.worker"],
  "python_files": ["toolsets.py"]
}
```

## Tasks
- [x] Add manifest loader + schema validation (JSON).
- [x] Define `ProjectManifest` Pydantic models in `llm_do/runtime/manifest.py` (single `entry`, required `version`, strict fields).
- [x] Resolve toolsets/workers/entries per manifest-driven linker flow.
- [x] Add `allow_cli_input` gating and `--input-json` support.
- [x] Remove CLI flags superseded by the manifest (entry/model/set/approval/max-depth/files).
- [x] Update CLI help/docs/tests to reflect new interface.
- [x] Update any example scripts or docs to use manifest format.
- [x] Run lint, typecheck, tests.

## Current State
Implementation complete. The manifest-driven CLI is now functional with:
- `ProjectManifest` Pydantic models in `llm_do/runtime/manifest.py`
- CLI accepts `llm-do project.json [prompt]` invocation
- `--input-json` for inline JSON input
- `allow_cli_input` gating for CLI overrides
- All lint, typecheck, and tests pass (322 tests)

## Notes
- Name collisions between workers/toolsets/entries must raise errors.
- `runtime` config is required in the manifest.
- Pydantic JSON parsing is strict JSON (no comments/trailing commas).
- `worker_files`/`python_files` lists should be non-empty strings, de-duped.
- `entry.input` is used when no CLI input is provided.
