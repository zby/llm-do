---
description: Analysis of non-streaming provider behavior and plan for graceful fallback support
---

# Non-Streaming Provider Support — Analysis & Plan

## 1. Analysis: What happens today with a non-streaming provider?

### The streaming decision chain

PydanticAI's `Model` base class defines two methods:

- **`request()`** — abstract, required. Returns a complete `ModelResponse`.
- **`request_stream()`** — optional, default raises `NotImplementedError`.

In `Agent.run()`, when `event_stream_handler` is provided, PydanticAI calls
`node.stream()` → `model.request_stream()`. Without the handler, it calls
`model.request()`.

In llm-do, the decision happens at `agent_runner.py:198`:

```python
if runtime.config.on_event is not None:
    # → passes event_stream_handler to agent.run()
    # → PydanticAI calls model.request_stream()
else:
    # → calls agent.run() without handler
    # → PydanticAI calls model.request()
```

### When is `on_event` set?

**Almost always.** Both `run_tui()` and `run_headless()` in `ui/runner.py`
call `_start_render_loop()`, which creates an `on_event` callback and passes
it to the Runtime. The only way `on_event` is `None` is when no display
backends are provided — an unusual configuration.

### The crash

If a model only implements `request()` (like `SimpleHTTPChatModel`,
`ToolCallingModel`, or `NullModel`), and the runtime has `on_event` set:

1. `agent_runner.py` takes the streaming path (line 198)
2. Passes `event_stream_handler` to `agent.run()`
3. PydanticAI calls `model.request_stream()`
4. Base class raises: `NotImplementedError("Streamed requests not supported by this <ModelName>")`
5. **The run crashes.**

### Why existing tests don't catch this

- `test_events.py` uses PydanticAI's `TestModel`, which **does** implement
  `request_stream()` (wraps the response in a `TestStreamedResponse`).
- `ToolCallingModel` is used in tests that don't set `on_event`.
- Live tests use real providers (Anthropic, OpenAI), which all support streaming.
- Nobody has tested a request-only model with a display backend.

### Models affected today

| Model | Has `request()` | Has `request_stream()` | Breaks with `on_event`? |
|-------|:---:|:---:|:---:|
| Anthropic models | Y | Y | No |
| OpenAI models | Y | Y | No |
| PydanticAI TestModel | Y | Y | No |
| `SimpleHTTPChatModel` | Y | N | **Yes** |
| `ToolCallingModel` | Y | N | **Yes** |
| `NullModel` | Y | N | N/A (never used for LLM calls) |


## 2. Fix: Graceful fallback in `agent_runner.py`

The fix is in `run_agent()`: catch `NotImplementedError` from the streaming
path and fall back to `request()` (non-streaming), while still emitting the
final response events so the UI layer works correctly.

**Location:** `llm_do/runtime/agent_runner.py`

**Approach:** Try streaming first. If the model raises `NotImplementedError`,
fall back to the non-streaming `agent.run()` path. Post-hoc, emit synthetic
events (at minimum a `FinalResultEvent`) so the UI layer still renders the
response. This is the simplest change — it keeps the streaming path as the
default and only falls back when necessary.

Concretely:

```python
async def run_agent(...):
    ...
    if runtime.config.on_event is not None:
        try:
            output, run_messages = await _run_with_event_stream(...)
        except NotImplementedError:
            # Model doesn't support streaming - fall back to non-streaming
            result = await agent.run(
                prompt, deps=runtime, model_settings=model_settings,
                message_history=message_history,
            )
            run_messages = _finalize_messages(spec.name, runtime, result)
            output = result.output
            # Emit final-result event so UI knows the run completed
            _emit_non_streamed_result(spec, runtime, result)
    else:
        ...
```


## 3. Test plan: Non-streaming provider across all examples

### Injection mechanism

The existing `register_model_factory()` + `LLM_DO_MODEL` env var provides a
clean injection point. No undocumented hacks needed.

**Strategy:** Create a `NonStreamingModel` wrapper that:
1. Takes any existing `Model` instance
2. Delegates `request()` to the wrapped model
3. Explicitly does **not** implement `request_stream()` (inherits the base
   class `NotImplementedError`)
4. Register it as `nostream:` provider prefix

```python
class NonStreamingModel(Model):
    """Wrapper that strips streaming support from any model."""
    def __init__(self, inner: Model):
        super().__init__()
        self._inner = inner

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def system(self) -> str:
        return self._inner.system

    async def request(self, messages, model_settings, model_request_parameters):
        return await self._inner.request(
            messages, model_settings, model_request_parameters
        )
```

Register:
```python
def build_nostream_model(model_name: str) -> NonStreamingModel:
    inner = infer_model(model_name)
    return NonStreamingModel(inner)

register_model_factory("nostream", build_nostream_model)
```

Usage: `LLM_DO_MODEL=nostream:anthropic:claude-haiku-4-5`

### Test structure

A single parametrized test in `tests/runtime/` that:
1. Builds each example via `_build_example()`
2. Runs it with a `NonStreamingModel`-wrapped `ToolCallingModel` (no API key needed)
3. Passes `on_event` callback (to trigger the streaming path)
4. Asserts the run completes without `NotImplementedError`

For live tests: a conftest marker `@pytest.mark.nostream` that reruns
selected live tests with `LLM_DO_MODEL=nostream:...` to verify real
providers work through the fallback path.


## 4. Implementation steps

1. Add `NotImplementedError` catch + fallback in `agent_runner.py:run_agent()`
2. Add helper to emit synthetic completion events for the non-streamed path
3. Create `NonStreamingModel` wrapper (in `llm_do/models.py` or a test util)
4. Add unit test: non-streaming model + `on_event` -> completes without error
5. Add unit test: non-streaming model + `on_event` -> UI events still emitted
6. Add parametrized test across examples with non-streaming model
7. Run lint, typecheck, tests


## Open Questions

- Should the fallback be silent, or should it log a warning (e.g. via
  `warnings.warn()`) so users know streaming is degraded?
- Should `SimpleHTTPChatModel` in the custom_provider example get a
  `request_stream()` implementation, or is it better left as-is to serve as
  a test case for the fallback?
- Could PydanticAI upstream add a `supports_streaming` property to `Model`
  so we can check before attempting, rather than catch-and-retry?
