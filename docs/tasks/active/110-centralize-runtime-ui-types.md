# Centralize Runtime + UI Types

## Status
information gathering

## Prerequisites
- [ ] none

## Goal
Centralize the *type surfaces* for both `ctx_runtime` and `ui` so it’s easy to find/import key contracts without collapsing everything into a single mega-module.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/ctx.py`: `Invocable`, `ModelType`, `EventCallback`, `WorkerRuntime`
  - `llm_do/ctx_runtime/invocables.py`: `WorkerInvocable`, `ToolInvocable`, `WorkerInput`
  - `llm_do/ctx_runtime/approval_wrappers.py`: `ApprovalPolicy`, `ApprovalCallback`
  - `llm_do/ctx_runtime/__init__.py`: runtime public exports
  - `llm_do/ui/events.py`: `UIEvent` + event classes
  - `llm_do/ui/display.py`: `DisplayBackend` (depends on `UIEvent`)
  - `llm_do/ui/parser.py`: `parse_event()` (raw PydanticAI → `UIEvent`)
  - `llm_do/ui/__init__.py`: UI public exports
- Related tasks/notes/docs:
  - `docs/ui.md`
  - `docs/architecture.md`
  - `docs/tasks/backlog/ui-architecture-improvements.md` (broader follow-up area)
- How to verify:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Prefer *facade modules* (re-export pattern) over moving every definition into a single `types.py`.
- Inputs:
  - Types are spread across many modules; hard to know “where the types live”.
  - Centralizing by *moving* definitions risks import cycles and hurts locality.
  - `__init__.py` files already act as public facades; we can build on this pattern.
- Options:
  1. Mega `types.py` (move definitions): simple imports, high cycle risk, loses locality.
  2. Facade `types.py` (re-export canonical definitions): “one place to import”, low risk, preserves locality.
  3. `contracts/` package: separate interface contracts from implementations, more files, clean layering.
- Outcome:
  - Pending, but likely start with (2) and revisit (3) if the type surface continues to grow.

## Tasks

### Runtime (`llm_do/ctx_runtime`)
- [ ] Inventory cross-module “contract” types that cause import churn (protocols, type aliases, callback types).
- [ ] Add `llm_do/ctx_runtime/types.py` (or `contracts.py`) as the central import surface for runtime contracts.
- [ ] Update internal imports to point at the contract module (minimize cross-imports between `ctx.py`, `invocables.py`, `approval_wrappers.py`).
- [ ] Confirm exports remain coherent (`llm_do/ctx_runtime/__init__.py`, `llm_do/__init__.py`).

### UI (`llm_do/ui`)
- [ ] Decide whether `llm_do/ui/__init__.py` remains the primary facade or if `llm_do/ui/types.py` is the preferred import surface.
- [ ] Add `llm_do/ui/types.py` (if useful) to re-export `UIEvent`, event subclasses, and backend interface types.
- [ ] (Optional) Split `llm_do/ui/events.py` into `llm_do/ui/events/` package modules (`base.py`, `tools.py`, `text.py`, etc.) and re-export from `events/__init__.py`.
- [ ] Keep `llm_do/ui/parser.py` as the only module that inspects raw `pydantic_ai.*` event types (avoid leaking upstream event types into the rest of the UI).

### Docs + Hygiene
- [ ] Update `docs/ui.md` and `docs/architecture.md` with the new “type map” / import surfaces.
- [ ] Run lint/typecheck/tests (`ruff`, `mypy`, `pytest`).

## Current State
Task created. No code changes yet.

## Notes
- Start with facades/re-exports; only move definitions if import cycles or coupling become a real problem.
- Keep changes behavior-preserving (pure refactor) unless a specific type boundary bug is discovered.
