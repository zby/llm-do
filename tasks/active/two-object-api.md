# Two-Object API for Invocable.call()

## Status
backlog

## Goal
Split the `Invocable.call()` signature to receive global config and per-call state as separate objects, making the scope distinction explicit at the API boundary.

**Before:**
```python
class Invocable(Protocol):
    async def call(
        self,
        input_data: Any,
        runtime: WorkerRuntimeProtocol,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any: ...
```

**After:**
```python
class Invocable(Protocol):
    async def call(
        self,
        input_data: Any,
        config: RuntimeConfig,                # global scope (immutable, shared)
        state: CallFrame,                     # per-call scope (mutable, forked)
        run_ctx: RunContext[WorkerRuntime],   # tools unchanged
    ) -> Any: ...
```

## Rationale

The runtime has two distinct scopes currently mixed in the API:

1. **Global Scope (RuntimeConfig)** - constant for entire run, shared across all workers:
   - `cli_model` - CLI-specified model
   - `run_approval_policy` - tool approval rules
   - `max_depth` - recursion limit
   - `on_event` - UI event callback
   - `verbosity` - output level
   - `usage` - UsageCollector (thread-safe sink)

2. **Per-Call Scope (CallFrame)** - mutable, forked per-worker:
   - `toolsets` - available tools for this worker
   - `model` - effective model (resolved)
   - `depth` - current call depth
   - `prompt` - current prompt
   - `messages` - message history

The current `WorkerRuntime` facade obscures this distinction. When you access `runtime.model` vs `runtime.max_depth`, they look identical but have fundamentally different semantics.

## Context

- Relevant files:
  - `llm_do/runtime/contracts.py` - `Invocable` protocol, `WorkerRuntimeProtocol`
  - `llm_do/runtime/worker.py` - `Worker.call()`, `ToolInvocable.call()`
  - `llm_do/runtime/context.py` - `WorkerRuntime`, `RuntimeConfig`, `CallFrame`, `_execute()`
  - `llm_do/runtime/runner.py` - `run_invocable()`

- Key constraint: PydanticAI's `RunContext[T]` expects a single deps type. Tools access `run_ctx.deps` to call other tools via `run_ctx.deps.call()`. Keep `WorkerRuntime` as deps type so tools don't change.

## Tasks

- [ ] Update `Invocable` protocol in `contracts.py`:
  ```python
  class Invocable(Protocol):
      async def call(
          self,
          input_data: Any,
          config: RuntimeConfig,
          state: CallFrame,
          run_ctx: RunContext[WorkerRuntimeProtocol],
      ) -> Any: ...
  ```

- [ ] Update `Worker.call()` in `worker.py`:
  - Change signature to receive `config` and `state` separately
  - Create child state via `state.fork()`
  - Build `WorkerRuntime(config=config, frame=child_state)` for agent deps
  - Access global config directly: `config.run_approval_policy`, `config.max_depth`, etc.
  - Access per-call state directly: `state.depth`, `state.model`, etc.

- [ ] Update `ToolInvocable.call()` in `worker.py`:
  - Change signature to receive `config` and `state` separately
  - Minimal changes - just use the toolset from state

- [ ] Update `WorkerRuntime._execute()` in `context.py`:
  - Pass `self.config` and `self.frame` separately to `entry.call()`
  ```python
  async def _execute(self, entry: Invocable, input_data: Any) -> Any:
      run_ctx = self._make_run_context(entry.name, self.model, self)
      return await entry.call(input_data, self.config, self.frame, run_ctx)
  ```

- [ ] Update any direct callers of `entry.call()` (search for `.call(` in runtime code)

- [ ] Update tests that mock or call `Invocable.call()` directly

- [ ] Verify tools still work via `run_ctx.deps.call()` pattern

## Verification

```bash
uv run pytest tests/runtime/ -v
uv run pytest tests/live/ -v  # if available
```

Check example still works:
```bash
cd examples/pitchdeck_eval_code_entry
# verify run_ctx.deps.call() pattern still works
```

## Risks / Edge Cases

- Tools access `run_ctx.deps` which is `WorkerRuntime` - this should NOT change
- `WorkerRuntime` properties must continue to delegate correctly to config/frame
- Message history propagation (`runtime.messages[:] = ...`) must still work
- Existing code using `runtime.spawn_child()` should still work (it's on WorkerRuntime)

## Notes

- This is Phase 1 of a 3-phase refactoring:
  - Phase 1: Two-Object API (this task)
  - Phase 2: Extract MessageAccumulator (separate task)
  - Phase 3: Immutable CallState (separate task)

- Future naming consideration: `RuntimeConfig` → `RunConfig`, `CallFrame` → `CallState`
