# Resolve Worker Models at Construction Time

## Status
completed

## Prerequisites
- [x] none

## Goal
Resolve each Worker's model exactly once at construction time using the worker's
own model or the `LLM_DO_MODEL` env fallback. Remove CLI/manifest overrides and
runtime compatibility checks; missing model should raise an error.

## Context
- Relevant files/symbols:
  - `llm_do/models.py` (`select_model`, `NoModelError`)
  - `llm_do/runtime/worker.py` (`Worker.__post_init__`, `_call_internal`)
  - `llm_do/runtime/registry.py` (worker construction, `.worker` parsing)
  - `llm_do/runtime/shared.py` (`Runtime._build_entry_frame`)
  - `llm_do/runtime/manifest.py` (entry config schema)
  - `llm_do/cli/main.py` (model selection)
  - Docs: `docs/cli.md`, `docs/reference.md`
  - Tests: `tests/runtime/test_model_resolution.py`, `tests/test_model_compat.py`
- Final behavior:
  - Worker model resolution happens in `Worker.__post_init__` and uses
    `LLM_DO_MODEL` as fallback.
  - `compatible_models` is only a constructor/`.worker` input and is not stored
    on `Worker`.
  - Runtime uses resolved `worker.model`; no per-call compatibility checks or
    overrides.
  - Missing model now raises `NoModelError`.

## Decision Record
- Decision: Resolve each Worker's model at construction time only; remove
  entry/CLI overrides and treat `LLM_DO_MODEL` as a fallback (not an override).
- Inputs: user direction to drop overrides, avoid silent ignore, and rely on env
  fallback for unset workers.
- Options considered:
  - A) Resolve once at construction with env fallback only (chosen)
  - B) Keep CLI/manifest overrides (rejected)
  - C) Keep runtime compatibility checks (rejected)
- Outcome: Implemented A and updated docs/tests.
- Follow-ups:
  - Document that `compatible_models` effectively signals "needs env fallback"
    (done in docs).

## Tasks
- [x] Resolve and store `Worker.model` during construction; drop runtime
  compatibility checks.
- [x] Remove CLI/manifest model overrides and update registry/runtime to use
  resolved models.
- [x] Update tests and docs to reflect new resolution behavior and env fallback.
- [x] Keep `LLM_DO_MODEL` as fallback; raise `NoModelError` when missing.

## Current State
Completed: models resolve once at construction, overrides removed, env fallback
documented, tests updated, checks passing.

## Notes
- `compatible_models` now only validates at construction time; workers without a
  model rely on the env fallback.
