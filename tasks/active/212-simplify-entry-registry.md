# Simplify entry registry and entry protocol

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Replace the Invocable/ToolInvocable abstractions with a minimal Entry protocol and
registry-focused linking model that keeps runtime orchestration intact while removing
double discovery and Worker-as-Toolset coupling.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/contracts.py` (Invocable protocol)
  - `llm_do/runtime/worker.py` (Worker, ToolInvocable, WorkerToolset)
  - `llm_do/runtime/registry.py` (build_invocable_registry, discovery/linking)
  - `llm_do/runtime/deps.py` (WorkerRuntime.run/call dispatch)
  - `llm_do/runtime/shared.py` (Runtime entry execution)
  - `llm_do/runtime/discovery.py` (module discovery)
  - `llm_do/cli/main.py` (CLI entry selection)
  - `llm_do/runtime/__init__.py` (public exports)
- Related tasks/notes/docs:
  - `tasks/completed/214-worker-toolset-adapter.md`
  - `docs/notes/toolsets-as-import-tables.md`
  - `docs/notes/worker-design-rationale.md`
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Keep entry method named `call()` for now to avoid collision with `Runtime.run()`.
- Inputs: Current runtime dispatch uses `entry.call()` and `Runtime.run()` already exists.
- Options: Rename entry method to `run()` now, or defer and keep `call()`.
- Outcome: Defer rename; keep `call()` in Entry for this change set.
- Follow-ups: Revisit naming if runtime API is renamed (`execute`, etc.).

## Tasks
- [ ] Define `Entry` protocol (name + toolsets + call) and have `Worker` conform.
- [ ] Implement `@entry` decorator + `EntryFunction` wrapper carrying toolset refs.
- [ ] Resolve toolset refs (names vs instances) during registry linking.
- [ ] Remove `ToolInvocable` and update registry/CLI to use Entry + decorator discovery.
- [ ] Rename `InvocableRegistry`/`build_invocable_registry` to Entry equivalents.
- [ ] Update runtime/CLI exports + docs/examples to reflect new entry flow.
- [ ] Run lint, typecheck, tests.

## Current State
Task created from the simplified registry plan; no code changes yet.

## Notes
- Toolset refs can be names or instances; runtime should only run with resolved instances.
- `ctx.call()` uses tool names, which may differ from toolset names.
- Preserve orchestration work (toolset resolution, schema refs, server-side tools).
