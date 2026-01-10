# Remove Redundant Validation Checks

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Remove redundant validation/duplicate-check logic that is already enforced by PydanticAI or later runtime layers, without changing intended behavior beyond error timing/messages.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/worker.py` (schema_in validation, model compatibility check)
  - `llm_do/models.py` (`select_model`, `validate_model_compatibility`)
  - `llm_do/runtime/registry.py` (duplicate entry/worker checks)
  - `llm_do/runtime/worker_file.py` (duplicate toolset entry check)
  - `.venv/lib/python3.13/site-packages/pydantic_ai/toolsets/combined.py` (tool name conflict enforcement)
  - `.venv/lib/python3.13/site-packages/pydantic_ai/_tool_manager.py` (tool args validation)
- Related tasks/notes/docs:
  - `tasks/backlog/multi-instance-toolsets.md` (prior note on duplicate check redundancy)
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Keep compatible_models checks per worker; keep early duplicate toolset entry error; move tool arg validation for direct calls into WorkerRuntime.call and skip schema_in validation for tool-invoked workers.
- Inputs: PydanticAI CombinedToolset conflict errors; ToolManager arg validation; requirement that compatible_models are per worker.
- Options:
  - Centralize direct-call tool arg validation in WorkerRuntime.call and skip Worker.call schema_in validation for tool calls.
  - Keep early duplicate toolset entry checks for clear config errors.
- Outcome: Proceeding with code changes; tests pending.
- Follow-ups: Update tests if error timing/messages change; run lint/typecheck/tests.

## Tasks
- [x] Confirm PydanticAI conflict behavior and arg validation paths are always exercised for tool-invoked workers.
- [x] Keep per-worker compatible_models validation (do not rely solely on select_model).
- [x] Keep duplicate toolset entry checks for early config errors.
- [x] Remove duplicate Python worker name check in registry (discovery already enforces it).
- [ ] Adjust/remove tests that assert removed checks; add replacements only if still needed.
- [ ] Run lint/typecheck/tests.

## Current State
Implemented direct tool arg validation in WorkerRuntime.call, skipped schema_in validation for tool-invoked workers, and removed redundant python worker duplicate check in registry. `uv run mypy llm_do` and `uv run pytest` passed; `uv run ruff check .` failed on unused import in `scripts/analyze_imports.py`.

## Notes
- Removing schema_in validation in `Worker.call()` changes where invalid inputs are caught; consider only skipping it for tool-invoked calls (if needed).
- Dropping the worker_file duplicate toolset entry check shifts errors to runtime and may change error type/message.
