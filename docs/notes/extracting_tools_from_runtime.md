# Dynamic Tool Loading Refactor

## Goal
Move the tool registration/dynamic loading logic out of `runtime.py` into a
standalone `tools.py` module so we can resolve the circular dependency on
`call_worker` via dependency injection.

## Review
> ⚠️ **User review required**
>
> `_register_worker_tools` will be renamed to `register_worker_tools` and moved to
> `tools.py`. The new helper needs an additional `worker_runner: Callable` argument
> so delegated calls stay pluggable.

## Proposed Changes

### `llm_do/tools.py` (new)
- Create the module.
- Move `_load_custom_tools` here (rename to `load_custom_tools`).
- Move `_register_worker_tools` here (rename to `register_worker_tools`).
- Update `register_worker_tools` to accept `worker_runner: Callable` and ensure
  `worker_call_tool` uses the injected runner instead of importing `call_worker`.

### `llm_do/runtime.py`
- Import `register_worker_tools` from `.tools`.
- Delete `_register_worker_tools`, `_load_custom_tools`,
  `_worker_call_tool_async`, and `_worker_create_tool`.
- Update `_default_agent_runner_async` to call `register_worker_tools`, passing a
  runner that wraps `call_worker_async` (or a small closure) so the tool module
  can perform delegation without reaching back into `runtime.py`.
- Alternatively, pass `call_worker_async` directly to the tool helper and let it
  construct the worker-call tool internally.

### `llm_do/types.py`
- No immediate code changes. Optionally add a `WorkerRunner` protocol if it
  helps document the callable signature used by `register_worker_tools`.

## Verification Plan
1. Run existing automated coverage, paying particular attention to
   `tests/test_custom_tools.py` and `tests/test_worker_delegation.py`.
   ```bash
   uv run pytest tests/
   ```
2. Manual verification is unnecessary if the automated suite passes.
