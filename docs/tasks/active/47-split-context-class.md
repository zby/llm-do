# Split and Rename `Context` Class

## Status
ready for implementation

## Prerequisites
- [x] `docs/tasks/completed/49-approval-unification.md` (removes `requires_approval` and `Context.approval`)
- [x] `docs/tasks/completed/50-rename-entry-to-invocable.md` (renames types before structural split)

## Goal
Rename `Context` to `WorkerRuntime` and split into `RuntimeConfig` (shared/immutable) + `CallFrame` (per-worker, forked on spawn). This separates dispatch mechanics from per-call state, enables correct concurrent worker support, and uses clearer naming.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/ctx.py`: `Context`, `ToolsProxy`, `Invocable` (protocol), `Context.from_entry()`, `Context.call()`, `Context._execute()`
  - `llm_do/ctx_runtime/invocables.py`: `WorkerInvocable`, `ToolInvocable` (concrete classes implementing `Invocable`)
  - `llm_do/ctx_runtime/cli.py`: context construction + approval toolset wrapping
  - `llm_do/ctx_runtime/discovery.py`: imports/exports WorkerInvocable
  - `llm_do/ctx_runtime/__init__.py`: public exports
  - Tests: `tests/runtime/test_context.py`, `tests/runtime/test_model_resolution.py`, `tests/runtime/test_events.py`
- Related notes/docs:
  - `docs/notes/reviews/review-solid.md` (Ctx runtime core finding)
- How to verify:
  - `uv run pytest`
- Invariants to preserve:
  - Tool calls must not mutate worker depth (`tests/runtime/test_context.py::test_depth_counts_only_workers`).
  - Model used for tool calls follows current precedence (invocable model overrides CLI model; otherwise CLI model wins) (`tests/runtime/test_model_resolution.py`).
  - Message history behavior: only top-level worker run uses persisted history; delegated workers start fresh.

## Decision Record
- Decision: **Option B** — Split into `RuntimeConfig` + `CallFrame`, with `WorkerRuntime` as the deps facade.
- Inputs:
  - `Context` currently mixes tool dispatch, model resolution, usage tracking, and UI event emission.
  - Workers pass `deps=ctx` into PydanticAI (`deps_type=type(ctx)`), so the facade (`WorkerRuntime`) remains the deps type.
  - Concurrent workers require per-call-chain state (`depth`, `prompt`, `messages`) to be forked, not shared.
- Naming:
  - `RuntimeConfig` — structurally immutable shared config (no per-call-chain state):
    - model resolver inputs (`cli_model`, env access) and/or `select_model` wrapper
    - `max_depth`
    - event sink + verbosity (`on_event`, `verbosity`) (thread-safe if shared)
    - usage sink/collector (thread-safe if shared)
    - (no `approval` field — removed by Task 49)
  - `CallFrame` — per-worker/per-branch state (forked on spawn):
    - `depth: int`
    - `prompt: str`
    - `messages: list[Any]` (or a message-history handle if we later need per-branch storage)
    - `toolsets: list[AbstractToolset[Any]]` (dispatch state)
    - `model: ModelType` (effective model for tool calls in this frame)
  - `WorkerRuntime` — facade over both, used as PydanticAI deps
- Why "Context" is problematic:
  - Overloaded term (React Context, Python contextvars, PydanticAI RunContext)
  - Doesn't communicate what the class actually does
- Entry → Invocable rename: See Task 50 (`docs/tasks/completed/50-rename-entry-to-invocable.md`)
  - Done as prerequisite before this task
  - Uses `Invocable` (protocol), `WorkerInvocable`, `ToolInvocable`, `invocables.py`
- Concurrency semantics:
  - `depth` is per-call-chain (local), not global
  - Spawning a child worker forks the `CallFrame` (child gets independent depth, messages)
  - Siblings don't affect each other's depth
  - `max_depth` is enforced per-branch
  - **Message history location**: `messages` lives in `CallFrame` (per-worker), NOT in `RuntimeConfig` (shared). Each forked frame gets its own message list to prevent concurrent workers from mutating a shared list. Top-level worker may receive persisted history; child frames start fresh.
- Follow-ups:
  - Consider a separate task to unify/centralize UI event emission (currently split between `WorkerRuntime.call()` and `Invocable` event parsing).

## Tasks
- [ ] Document current invariants (depth behavior, message history sharing, usage aggregation) to preserve during refactor
- [ ] Classify `Context` fields into `RuntimeConfig` (shared) vs `CallFrame` (per-worker)
- [ ] Create `RuntimeConfig` class with:
  - Model resolver inputs/wrapper
  - Event sink (`on_event`) + `verbosity` (document concurrency assumptions)
  - Usage sink/collector (document concurrency assumptions)
  - `max_depth`, `cli_model`
  - (no `approval` — already removed by Task 49)
- [ ] Create `CallFrame` class with:
  - `depth: int`
  - `prompt: str`
  - `messages: list`
  - `toolsets: list[AbstractToolset[Any]]`
  - `model: ModelType`
  - `fork()` method that creates independent child frame with incremented depth
  - `clone_same_depth()` (or similar) to support “swap toolsets/model without changing depth” (current `_clone` behavior)
- [ ] Create `WorkerRuntime` facade:
  - Holds `config: RuntimeConfig` + `frame: CallFrame`
  - Exposes the minimal deps API used by tool code/tests (`call()`, `tools`, `depth`, `max_depth`, `messages`, etc.)
  - `spawn_child()` returns new `WorkerRuntime` with forked `CallFrame`, same `RuntimeConfig`
  - `with_frame()`/`with_toolsets_model()` helper for same-depth context preparation in `_execute`
- [ ] Extract tool lookup/call mechanics into `ToolDispatcher` (or keep on facade), including:
  - input coercion (`coerce_worker_input` vs `{"input": ...}`)
  - `ToolCallEvent` / `ToolResultEvent` emission and call-id generation
- [ ] Rename `Context` → `WorkerRuntime` across codebase
- [ ] Update runtime call sites and tests to match the new structure
- [ ] Run `uv run pytest`

## Current State
Decision made: Split `Context` into `RuntimeConfig` + `CallFrame` with `WorkerRuntime` facade. Prerequisites complete; task is ready to implement.

**Scope**: Structural refactoring only (Context split + rename to WorkerRuntime).

## Notes
- `CallFrame.fork()` is the key to concurrency correctness — each spawned worker gets an independent frame.
- "Context" → "WorkerRuntime" rename improves clarity and avoids collision with overloaded "context" terminology.

### Approval Unification (PREREQUISITE — Task 49)
See `docs/tasks/completed/49-approval-unification.md`.

Task 49 removes `requires_approval` and `Context.approval` before this task runs, so this refactoring doesn't need to migrate approval logic.
