# Refactor Entry Abstraction

## Status
completed

## Prerequisites
- [x] none

## Goal
Replace EntrySpec with a single Entry abstraction (base + subclasses) so entry execution is uniform without wrapper hacks.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/contracts.py` (EntrySpec, AgentSpec)
  - `llm_do/runtime/runtime.py` (run_entry, run)
  - `llm_do/runtime/registry.py` (build_entry linking)
  - `llm_do/cli/main.py` (run flow)
  - `llm_do/ui/runner.py` (entry execution path)
  - `docs/reference.md`, `README.md` (public API docs)
  - tests referencing `EntrySpec` / `build_entry` / `run_entry`
- Related tasks/notes/docs:
  - N/A (decision made in chat to deprecate EntrySpec)
- How to verify / reproduce:
  - `uv run pytest`
  - `uv run mypy llm_do`
  - `uv run ruff check .`

## Decision Record
- Decision: Deprecate `EntrySpec` and introduce `Entry` base type with two subclasses: `FunctionEntry` and `AgentEntry`.
- Inputs: Double-normalization and role-confusion from EntrySpec acting as both boundary adapter and agent wrapper.
- Options:
  - Keep EntrySpec + add entry target unions (rejected; too much branching).
  - New Entry base with subclasses (chosen).
- Outcome: Build and run paths accept `Entry` only; agent entries no longer wrapped by EntrySpec.
- Follow-ups:
  - Remove EntrySpec from public API once call sites are migrated (optional staged deprecation).

## Tasks
- [x] Define `Entry` base type and `FunctionEntry`/`AgentEntry` implementations.
- [x] Update runtime to call `entry.run(...)` (single execution path).
- [x] Update `build_entry(...)` to return `Entry` + registry (agent entry -> AgentEntry, python entry -> FunctionEntry).
- [x] Update CLI/UI to accept `Entry` (no unions).
- [x] Update tests and docs/examples referencing `EntrySpec` or `run_entry` accordingly.
- [x] Remove or deprecate `EntrySpec` and adjust exports.

## Current State
Entry abstraction refactor complete: added `Entry` + `FunctionEntry`/`AgentEntry`, runtime now uses `entry.run(...)`,
build_entry returns `Entry`, CLI/UI/types/exports updated, and docs/tests/examples migrated. Checks run:
`uv run ruff check .`, `uv run mypy llm_do`, `uv run pytest`.

## Notes
- Keep code changes minimal; avoid introducing separate entrypoint dispatch methods.
- Consider a brief deprecation shim only if required by external tests.
