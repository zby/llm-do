# Split and Rename `Context` Class

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Rename `Context` to `WorkerRuntime` and split into `RuntimeConfig` (shared/immutable) + `CallFrame` (per-worker, forked on spawn). Also rename `WorkerEntry` to `Invocable`. This separates policy (model selection, approval) from dispatch mechanics, enables correct concurrent worker support, and uses clearer naming.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/ctx.py`: `Context`, `ToolsProxy`, `Context.from_entry()`, `Context.call()`, `Context._execute()`
  - `llm_do/ctx_runtime/entries.py`: `WorkerEntry` (→ `Invocable`), depends on `ctx.depth`, `ctx.max_depth`, `ctx._child()`, `ctx.on_event`, `ctx.messages`
  - `llm_do/ctx_runtime/cli.py`: context construction + approval toolset wrapping
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
- Why "Entry" → "Invocable":
  - "Entry" sounds like "entrypoint" or "entry worker"
  - Actually represents a unified abstraction for callable units (both tools and workers)
  - "Invocable" clearly communicates "something you can invoke/call"
  - `WorkerEntry` → `Invocable`, `entries.py` → `invocables.py`
- Concurrency semantics:
  - `depth` is per-call-chain (local), not global
  - Spawning a child worker forks the `CallFrame` (child gets independent depth, messages)
  - Siblings don't affect each other's depth
  - `max_depth` is enforced per-branch
- Follow-ups:
  - Consider a separate task to unify/centralize UI event emission (currently split between `WorkerRuntime.call()` and `Invocable` event parsing).
  - Remove `requires_approval` field from Invocables — approval should be unified via `ApprovalToolset` only (see Approval Unification note below).

## Tasks
- [ ] Document current invariants (depth behavior, message history sharing, usage aggregation) to preserve during refactor
- [ ] Classify `Context` fields into `RuntimeConfig` (shared) vs `CallFrame` (per-worker)
- [ ] Create `RuntimeConfig` class with:
  - Model resolver inputs/wrapper
  - Event sink (`on_event`) + `verbosity` (document concurrency assumptions)
  - Usage sink/collector (document concurrency assumptions)
  - `max_depth`, `cli_model`
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
- [ ] Rename `WorkerEntry` → `Invocable` across codebase (including `entries.py` → `invocables.py`)
- [ ] Update runtime call sites and tests to match the new structure
- [ ] Run `uv run pytest`

## Current State
Decision made: Split `Context` into `RuntimeConfig` + `CallFrame` with `WorkerRuntime` facade, and rename `WorkerEntry` to `Invocable`. Ready to implement.

## Notes
- `CallFrame.fork()` is the key to concurrency correctness — each spawned worker gets an independent frame.
- "Context" → "WorkerRuntime" rename improves clarity and avoids collision with overloaded "context" terminology.
- "WorkerEntry" → "Invocable" rename clarifies that it's a callable unit (tool or worker), not an entrypoint.

### Approval Unification
Currently there are two redundant approval mechanisms:
1. `requires_approval` flag on Invocables + `Context.approval()` function — static, per-invocable
2. `ApprovalToolset` wrapping — dynamic, can inspect args/context

These should be unified: remove `requires_approval` from Invocables and use `ApprovalToolset` exclusively.
- User-initiated top-level calls don't need approval (user already consented)
- LLM-initiated nested calls go through `ApprovalToolset`
- `ApprovalToolset.needs_approval()` or config handles the decision

This removes `Context.approval` field from `RuntimeConfig` and simplifies the approval model.
