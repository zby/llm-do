# Remove CallFrame.fork Fallbacks

## Status
waiting for resolve-worker-models-at-construction (expected soon)

## Prerequisites
- [ ] resolve-worker-models-at-construction (recommended to complete first; proceed after it lands)

## Goal
Remove inheritance fallbacks from `CallFrame.fork()` and `spawn_child()`, making all parameters required. This makes data flow explicit and eliminates dead code paths in production.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/call.py` (`CallFrame.fork`)
  - `llm_do/runtime/deps.py` (`WorkerRuntime.spawn_child`)
  - `llm_do/runtime/contracts.py` (`WorkerRuntimeProtocol.spawn_child`)
  - `tests/runtime/test_model_resolution.py` (uses fallbacks for testing)
  - `tests/runtime/test_events.py` (uses fallbacks for testing)
- Current behavior:
  - `fork()` accepts optional `active_toolsets`, `model`, and `invocation_name`
  - If not provided, values are inherited from parent's config
  - Production code (worker.py) always provides all parameters explicitly
  - Only test code uses the fallbacks
- Desired behavior:
  - All parameters required (no fallbacks)
  - Explicit data flow at all call sites
  - Prefer `Sequence`/`tuple` for `active_toolsets` params to avoid forcing `list(...)`
    conversions; fork still normalizes to tuple for storage
  - `test_child_context_uses_parent_model` currently asserts inheritance; it should be
    removed or repurposed to an explicit model pass-through test

## Decision Record
- Decision: Remove fallbacks, make parameters required
- Rationale: Production code never uses fallbacks; explicit is better than implicit
- Related: Complements model resolution task - if models are resolved at construction, inheritance is unnecessary
- Decision: Use `Sequence[AbstractToolset[Any]]` (or `tuple[...]`) for `active_toolsets`
  params so callers can pass the existing tuple without `list(...)`
- Decision: Add a regression test that missing required args raises `TypeError` to
  enforce the no-fallbacks contract

## Tasks
- [ ] Update `CallFrame.fork()` signature to require all parameters and accept
  `Sequence`/`tuple` for `active_toolsets` (normalize to tuple as before)
- [ ] Update `WorkerRuntime.spawn_child()` signature to require all parameters and
  accept `Sequence`/`tuple` for `active_toolsets`
- [ ] Update `WorkerRuntimeProtocol.spawn_child()` in contracts.py to match
- [ ] Update `test_model_resolution.py`: remove/repurpose the inheritance test and
  provide explicit `active_toolsets`, `model`, and `invocation_name`
- [ ] Update `test_events.py` to pass explicit values when calling `spawn_child`
- [ ] Add a regression test that calling `spawn_child()` without required args raises
  `TypeError` (no fallbacks)
- [ ] Verify no other call sites rely on fallbacks (worker.py, helpers, tests)

## Current State
Task updated with required signature changes, testing updates, and no-fallback
regression coverage.

## Notes
- Consider doing this after model resolution task, as that task also touches spawn_child call sites
- The tuple normalization (`tuple(active_toolsets)`) should remain in fork()
