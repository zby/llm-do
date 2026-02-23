# Simplify entry registry and entry protocol

## Status
completed

## Prerequisites
- [x] none

## Goal
Replace the Invocable/ToolInvocable abstractions with a minimal Entry protocol and
registry-focused linking model that keeps runtime orchestration intact while removing
double discovery and Worker-as-Toolset coupling.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/contracts.py` (Entry protocol, Invocable alias)
  - `llm_do/runtime/worker.py` (Worker, ToolInvocable, WorkerToolset, EntryFunction, @entry)
  - `llm_do/runtime/registry.py` (build_entry_registry, EntryRegistry)
  - `llm_do/runtime/deps.py` (WorkerRuntime.run/call dispatch)
  - `llm_do/runtime/shared.py` (Runtime entry execution)
  - `llm_do/runtime/discovery.py` (module discovery, discover_entries_from_module)
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
- [x] Define `Entry` protocol (name + toolsets + call) and have `Worker` conform.
- [x] Implement `@entry` decorator + `EntryFunction` wrapper carrying toolset refs.
- [x] Resolve toolset refs (names vs instances) during registry linking.
- [x] Update registry/CLI to use Entry + decorator discovery (ToolInvocable kept deprecated).
- [x] Rename `InvocableRegistry`/`build_invocable_registry` to Entry equivalents.
- [x] Update runtime/CLI exports + docs/examples to reflect new entry flow.
- [x] Run lint, typecheck, tests.

## Current State
Implementation complete. All lint, type checks, and tests pass.

## Implementation Summary
1. **Entry protocol** (`contracts.py`): Defined `Entry` protocol with `name`, `toolsets`, and `call()`. `Invocable` is now a backwards compatibility alias.

2. **@entry decorator** (`worker.py`): Added `EntryFunction` class and `@entry` decorator for marking Python functions as entry points with toolset refs.

3. **ToolInvocable conformance** (`worker.py`): Added `toolsets` property to ToolInvocable for Entry protocol compliance. Marked as deprecated.

4. **Registry linking** (`registry.py`):
   - Renamed to `EntryRegistry` and `build_entry_registry` (with backwards compat aliases)
   - Added discovery of `@entry` decorated functions via `load_all_from_files`
   - Toolset ref resolution for EntryFunction during registry linking

5. **Discovery** (`discovery.py`): Added `discover_entries_from_module` and `load_all_from_files` for unified discovery.

6. **Exports** (`__init__.py`): Added Entry, EntryRegistry, EntryFunction, entry, ToolsetRef, and related discovery functions.

## Notes
- Toolset refs can be names or instances; runtime only runs with resolved instances.
- `ctx.call()` uses tool names, which may differ from toolset names.
- Preserve orchestration work (toolset resolution, schema refs, server-side tools).
- ToolInvocable is kept for backwards compatibility but marked deprecated.
