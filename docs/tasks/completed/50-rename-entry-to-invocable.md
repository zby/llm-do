# Rename Entry → Invocable

## Status
completed

## Prerequisites
- [x] `docs/tasks/completed/49-approval-unification.md` (removes `requires_approval` field first)

## Goal
Rename Entry types to Invocable across the codebase. This clarifies that the abstraction represents "something you can invoke" (tool or worker), not an "entrypoint".

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/ctx.py`: `Invocable` (protocol)
  - `llm_do/ctx_runtime/invocables.py`: `Worker`, `ToolInvocable` (classes)
  - `llm_do/ctx_runtime/discovery.py`: imports/exports Worker
  - `llm_do/ctx_runtime/__init__.py`: public exports
  - `llm_do/ctx_runtime/cli.py`: uses Worker, ToolInvocable
  - `llm_do/__init__.py`: public exports
  - `experiments/`: references runtime types (e.g. `experiments/inv/v2_direct/run.py`)
  - Docs: `docs/architecture.md`, `docs/cli.md`
  - Tests: various test files reference these types
- Related tasks/notes/docs:
  - `docs/tasks/active/47-split-context-class.md` (depends on this task)
  - `docs/tasks/completed/49-approval-unification.md` (prerequisite)
- How to verify:
  - `uv run pytest`

## Decision Record
- Decision: Rename Entry types to Invocable
- Naming mapping:
  - `CallableEntry` (protocol) → `Invocable`
  - `WorkerEntry` (class) → `Worker`
  - `ToolEntry` (class) → `ToolInvocable`
  - `entries.py` → `invocables.py`
  - `discover_entries_from_module()` → `discover_workers_from_module()`
  - `load_entries_from_files()` → `load_workers_from_files()`
- Rationale:
  - "Entry" sounds like "entrypoint" or "entry worker"
  - "Invocable" clearly communicates "something you can invoke/call"
  - Matches the unified abstraction for tools and workers
- Non-goals:
  - Keep CLI “entrypoint” terminology (e.g., `--entry`, `entry_name`, “entry point”) since it refers to selecting which invocable to run, not the invocable types themselves.

## Tasks
- [x] Rename `CallableEntry` → `Invocable` in `ctx.py`
- [x] Rename `entries.py` → `invocables.py`
- [x] Rename `WorkerEntry` → `Worker` in `invocables.py`
- [x] Rename `ToolEntry` → `ToolInvocable` in `invocables.py`
- [x] Rename `discover_entries_from_module()` → `discover_workers_from_module()` and update call sites
- [x] Rename `load_entries_from_files()` → `load_workers_from_files()` and update call sites
- [x] Update `llm_do/ctx_runtime/discovery.py` imports/exports and docstrings
- [x] Update `llm_do/ctx_runtime/__init__.py` exports
- [x] Update `llm_do/__init__.py` exports
- [x] Update `cli.py` references
- [x] Update `experiments/` references (e.g., `experiments/inv/v2_direct/run.py`)
- [x] Update high-signal docs (`docs/architecture.md`, `docs/cli.md`) to match new names
- [x] Update all test files
- [x] Run `uv run pytest`

## Current State
Implementation complete; `uv run pytest` passed.

## Notes
- Pure rename task — no structural or behavioral changes
- Task 47 (Split Context) depends on this for clean naming
- When verifying, `rg` for `WorkerEntry`, `ToolEntry`, `CallableEntry`, and `ctx_runtime/entries.py` to ensure no stragglers remain (excluding true “entrypoint” CLI text like `--entry`).
