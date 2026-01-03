# Centralize Runtime + UI Types

## Status
complete

## Prerequisites
- [ ] none

## Goal
Centralize the *type surfaces* for both `runtime` and `ui` so it’s easy to find/import key contracts without collapsing everything into a single mega-module.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/contracts.py`: `Invocable`, `ModelType`, `EventCallback`, `WorkerRuntimeProtocol`
  - `llm_do/runtime/context.py`: `WorkerRuntime`
  - `llm_do/runtime/worker.py`: `Worker`, `ToolInvocable`, `WorkerInput`
  - `llm_do/runtime/approval.py`: `ApprovalPolicy`, `ApprovalCallback`
  - `llm_do/runtime/__init__.py`: runtime public exports
  - `llm_do/toolsets/loader.py`: `ToolsetBuildContext` (runtime-facing construction context)
  - `llm_do/ui/events.py`: `UIEvent` + event classes
  - `llm_do/ui/display.py`: `DisplayBackend` (depends on `UIEvent`)
  - `llm_do/ui/parser.py`: `parse_event()` (raw PydanticAI → `UIEvent`)
  - `llm_do/ui/__init__.py`: UI public exports
- Related tasks/notes/docs:
  - `docs/ui.md`
  - `docs/architecture.md`
  - `tasks/backlog/ui-architecture-improvements.md` (broader follow-up area)
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
  - Add `llm_do/runtime/contracts.py` as the canonical import surface for shared runtime contracts (type aliases + protocols), and type `Worker` against a protocol to avoid `context.py` ↔ `worker.py` cycles.

## Inventory

### Runtime Contract Types

**Protocols (abstract interfaces):**
- `Invocable` (`runtime/contracts.py`) - Protocol for dispatchable entries (workers, tools)
- `WorkerRuntimeProtocol` (`runtime/contracts.py`) - Protocol for the runtime deps surface used by workers

**Type Aliases:**
- `ModelType` (`runtime/contracts.py`) - `str` alias for model identifiers
- `EventCallback` (`runtime/contracts.py`) - `Callable[[UIEvent], None]` for UI event handling
- `ApprovalCallback` (`approval.py:19`) - `Callable[[ApprovalRequest], ApprovalDecision | Awaitable[...]]`

**Configuration Types:**
- `ApprovalPolicy` (`approval.py:26`) - Execution-time approval configuration
- `ToolsetBuildContext` (`toolsets/loader.py:31`) - Context for toolset construction

**Implementation Types (NOT for types.py - keep in current modules):**
- `Worker`, `ToolInvocable`, `WorkerInput` - Concrete entry implementations
- `WorkerRuntime`, `RuntimeConfig`, `CallFrame` - Runtime internals
- `UsageCollector`, `ToolsProxy` - Internal helpers

### Import Churn Patterns Found

1. **Circular dependency** between `context.py` ↔ `worker.py`:
   - `worker.py` imported `ModelType`, `WorkerRuntime` via `TYPE_CHECKING` guard (fragile)
   - Fix: move shared type aliases/protocols to `runtime/contracts.py` and type workers against `WorkerRuntimeProtocol`

2. **Import scatter** in consumers:
   - `cli/main.py` imports from 3 different runtime modules:
     - `ApprovalCallback`, `ApprovalPolicy` from `runtime.approval`
     - `EventCallback`, `Invocable` from `runtime.contracts`
     - `WorkerRuntime` from `runtime.context`
     - `ToolInvocable`, `Worker` from `runtime.worker`

3. **Cross-module dependencies**:
   - `approval.py` → `worker.py` (for `ToolInvocable`, `Worker`)
   - `runner.py` → `context.py`, `approval.py`, `worker.py`

### Missing Exports in `runtime/__init__.py`

Currently exported: `Invocable`, `ModelType`, `ApprovalPolicy`, `WorkerRuntime`, `Worker`, `ToolInvocable`, etc.

**Missing** (causing direct submodule imports):
- `EventCallback` (from `runtime/contracts.py`)
- `ApprovalCallback` (from `approval.py`)

Fix: Add these to `runtime/__init__.py` and update consumers to use the facade.

## Tasks

### Runtime (`llm_do/runtime`)
- [x] Inventory cross-module "contract" types that cause import churn (protocols, type aliases, callback types).
- [x] Add `llm_do/runtime/contracts.py` and move shared aliases/protocols (`ModelType`, `EventCallback`, `Invocable`).
- [x] Update `llm_do/runtime/worker.py` to depend on `WorkerRuntimeProtocol` (remove `TYPE_CHECKING` import cycle).
- [x] Update downstream imports (`runtime/__init__.py`, `runtime/runner.py`, `cli/main.py`).
- [x] Re-export `EventCallback`/`ApprovalCallback` from `runtime/__init__.py` and update `cli/main.py` to use facade imports.

### UI (`llm_do/ui`)
- [x] Verify `ui/__init__.py` exports all needed types (confirmed complete).
- [x] Update `cli/main.py` to use `..ui` facade imports.
- [ ] (Optional/Deferred) Split `llm_do/ui/events.py` into `llm_do/ui/events/` package if it grows too large.

### Hygiene
- [x] Run lint/typecheck/tests (`ruff`, `mypy`, `pytest`) - all pass.

## Current State
Complete. Runtime contracts in `llm_do/runtime/contracts.py`; all callback types exported from facades; `cli/main.py` uses clean facade imports for both `runtime` and `ui`.

## Notes
- Keep changes behavior-preserving (pure refactor).
