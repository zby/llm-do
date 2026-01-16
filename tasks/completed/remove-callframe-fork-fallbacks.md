# Remove CallFrame.fork Fallbacks

## Status
completed

## Prerequisites
- [ ] none (resolve-worker-models-at-construction is included in this task)

## Goal
Remove inheritance fallbacks from `CallFrame.fork()` and `spawn_child()`, making all parameters required, include the NullModel/entry tool-plane `RunContext` behavior, and resolve worker models at construction. This makes data flow explicit and eliminates dead code paths in production.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/call.py` (`CallFrame.fork`)
  - `llm_do/runtime/deps.py` (`WorkerRuntime.spawn_child`)
  - `llm_do/runtime/contracts.py` (`WorkerRuntimeProtocol.spawn_child`)
  - `llm_do/runtime/shared.py` (`Runtime.run_entry`, `_build_entry_frame`)
  - `llm_do/runtime/worker.py` (`Worker.__post_init__`)
  - `llm_do/models.py` (NullModel to satisfy RunContext when no worker model)
  - resolve-worker-models-at-construction (folded into this task)
  - `tests/runtime/test_model_resolution.py` (uses fallbacks for testing)
  - `tests/runtime/test_events.py` (uses fallbacks for testing)
  - `tests/runtime/helpers.py` (`build_runtime_context`)
- Current behavior:
  - `fork()` accepts optional `active_toolsets`, `model`, and `invocation_name`
  - If not provided, values are inherited from parent's config
  - Production code (worker.py) always provides all parameters explicitly
  - Only test code uses the fallbacks
  - Entry functions resolve a model via `select_model`, using `LLM_DO_MODEL` fallback
- Desired behavior:
  - All parameters required (no fallbacks)
  - Explicit data flow at all call sites
  - Prefer `Sequence`/`tuple` for `active_toolsets` params to avoid forcing `list(...)`
    conversions; fork still normalizes to tuple for storage
  - `test_child_context_uses_parent_model` currently asserts inheritance; it should be
    removed or repurposed to an explicit model pass-through test
  - Entry functions always use NullModel for tool-plane `RunContext`, ignoring
    `LLM_DO_MODEL` for now
  - NullModel is set explicitly at entry-frame construction (e.g.
    `Runtime._build_entry_frame` for `EntryFunction` paths), since
    `CallConfig.model` is required
  - NullModel hard-fails if used for LLM calls (fail-fast guardrail)
- How to verify / reproduce:
  - `uv run pytest tests/runtime/test_model_resolution.py tests/runtime/test_events.py`
  - Add targeted regression tests for missing required args (fork/spawn_child)
  - Add a NullModel hard-fail regression test for entry tool-plane LLM usage

## Decision Record
- Decision: Remove fallbacks, make parameters required
- Rationale: Production code never uses fallbacks; explicit is better than implicit
- Related: Complements model resolution task - if models are resolved at construction, inheritance is unnecessary
- Decision: Use `Sequence[AbstractToolset[Any]]` (or `tuple[...]`) for `active_toolsets`
  params so callers can pass the existing tuple without `list(...)`
- Decision: Add a regression test that missing required args raises `TypeError` to
  enforce the no-fallbacks contract
- Decision: Use a NullModel sentinel for tool-plane `RunContext`; entry functions
  should not require a model and should always use NullModel for now
- Decision: Worker tool calls should continue to pass the worker's model explicitly
- Decision: Keep the NullModel/entry tool-plane behavior in scope for this task
- Decision: Complete resolve-worker-models-at-construction as part of this task
- Decision: Resolve worker models in `Worker.__post_init__` only (no per-run overrides)
- Decision: Entry functions always use NullModel for tool-plane `RunContext` (ignore
  `LLM_DO_MODEL` for now)
- Decision: NullModel should raise a clear error if used for LLM calls

## Tasks
- [x] Add NullModel sentinel (likely in `llm_do/models.py`) and wire into tool-plane
  RunContext creation for entry functions (explicitly set in
  `Runtime._build_entry_frame` or the `EntryFunction` branch of `Runtime.run_entry`)
- [x] Add hard-fail behavior for NullModel (clear error on LLM call) and a regression
  test that exercising an LLM call through NullModel raises
- [x] Ensure entry functions always use NullModel without weakening `NoModelError`
  for workers
- [x] Update helpers/tests/entry frame to use NullModel for entry tool calls
- [x] Adjust model-resolution tests to reflect NullModel behavior for entry tool calls
- [x] Update docs (`docs/cli.md`, `docs/reference.md`) for construction-time worker
  model resolution and entry function NullModel fallback
- [x] Update `CallFrame.fork()` signature to require all parameters and accept
  `Sequence`/`tuple` for `active_toolsets` (normalize to tuple as before)
- [x] Update `WorkerRuntime.spawn_child()` signature to require all parameters and
  accept `Sequence`/`tuple` for `active_toolsets`
- [x] Update `WorkerRuntimeProtocol.spawn_child()` in contracts.py to match
- [x] Update `test_model_resolution.py`: remove/repurpose the inheritance test and
  provide explicit `active_toolsets`, `model`, and `invocation_name`
- [x] Update `test_events.py` to pass explicit values when calling `spawn_child`
- [x] Add a regression test that calling `spawn_child()` without required args raises
  `TypeError` (no fallbacks)
- [x] Add a regression test that calling `CallFrame.fork()` without required args raises
  `TypeError` (no fallbacks)
- [x] Verify no other call sites rely on fallbacks (worker.py, helpers, tests)
- [x] Audit model resolution paths to ensure worker models are resolved once at
  construction; remove any remaining runtime overrides or per-call compatibility
  checks for workers

## Current State
Completed: NullModel hard-fail behavior implemented, entry functions use it
explicitly, fallbacks removed, docs/tests updated, and checks passing.

## Notes
- Coordinate model resolution changes with spawn_child call-site updates
- The tuple normalization (`tuple(active_toolsets)`) should remain in fork()
- There is a completed resolve-worker-models-at-construction task; this task
  includes a verification pass to confirm invariants still hold
