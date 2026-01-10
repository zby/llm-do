# Simplify runtime/worker.py

## Context
Review of `llm_do/runtime/worker.py` and local imports (`llm_do/runtime/approval.py`, `llm_do/runtime/call.py`, `llm_do/runtime/contracts.py`, `llm_do/runtime/input_utils.py`, `llm_do/runtime/shared.py`, `llm_do/models.py`, `llm_do/toolsets/approval.py`, `llm_do/ui/events.py`, `llm_do/ui/parser.py`) to identify simplification opportunities.

## Findings

### 1) Unify model resolution and compatibility checks (redundant validation, duplicated derived values)
Current code (in `Worker._call_internal`):
```python
resolved_model = self.model if self.model is not None else state.model
if self.compatible_models is not None:
    model_str = get_model_string(resolved_model)
    compat_result = validate_model_compatibility(
        model_str, self.compatible_models, worker_name=self.name
    )
    if not compat_result.valid:
        raise ModelCompatibilityError(compat_result.message)
```
Proposed simplification (reuse model resolution path already used by `Runtime._build_entry_frame`):
```python
resolved_model = select_model(
    worker_model=self.model,
    cli_model=state.model,
    compatible_models=self.compatible_models,
    worker_name=self.name,
)
```
Judgment call: `select_model` only validates string models today. If compatibility checks must also apply to `Model` instances, either extend `select_model` to normalize `Model` via `get_model_string`, or keep a small follow-on check in `_call_internal` for non-string models.
Inconsistency prevented: yes. Entry runs reject `model` + `compatible_models` via `select_model`, but nested worker calls currently allow it. Centralizing would make behavior consistent.

### 2) Remove the `validate_input` flag in `_call_internal` (redundant parameter)
Current code:
```python
return await self._call_internal(
    input_data,
    config,
    state,
    run_ctx,
    validate_input=True,
)
```
```python
return await self._call_internal(
    tool_args,
    run_ctx.deps.config,
    run_ctx.deps.frame,
    run_ctx,
    validate_input=False,
)
```
Proposed simplification (push validation into a small helper and remove the flag):
```python
def _prepare_input(self, input_data: Any, *, validate: bool) -> Any:
    input_data = coerce_worker_input(self.schema_in, input_data)
    if validate and self.schema_in is not None:
        return self.schema_in.model_validate(input_data)
    return input_data

async def call(...):
    input_data = self._prepare_input(input_data, validate=True)
    return await self._call_internal(input_data, config, state, run_ctx)

async def call_tool(...):
    input_data = self._prepare_input(input_data, validate=False)
    return await self._call_internal(input_data, config, state, run_ctx)
```
Judgment call: none if both entry paths should keep the same coercion order; this just removes a boolean toggle in the internal API.
Inconsistency prevented: not directly, but it removes a footgun where future call sites could pass the wrong `validate_input` value.

### 3) Centralize message logging + history sync (duplicated derived values)
Current code (similar patterns appear in `_call_internal`, `_run_with_event_stream`, and `_run_streaming`):
```python
child_runtime.log_messages(self.name, child_state.depth, _get_all_messages(result))
if _should_use_message_history(child_runtime):
    _update_message_history(child_runtime, result)
    state.messages[:] = _get_all_messages(result)
```
Proposed simplification (single helper to log and sync):
```python
def _finalize_messages(
    self,
    runtime: WorkerRuntimeProtocol,
    state: CallFrame,
    result: Any,
) -> list[Any]:
    messages = _get_all_messages(result)
    runtime.log_messages(self.name, runtime.depth, messages)
    if _should_use_message_history(runtime):
        runtime.messages[:] = messages
        state.messages[:] = messages
    return messages
```
Use `_finalize_messages` in all three paths; keep tool-event emission separate (it sometimes needs `result.new_messages()`).
Judgment call: ensure this helper does not hide the ordering needed for tool-event fallback logic.
Inconsistency prevented: yes. Today `_get_all_messages` is called multiple times; if the underlying API changes or becomes lazy, runtime and state messages could diverge.

### 4) Tool event fallback duplicates parsing and drops `args_json` (duplicated derived values)
Current code (in `_emit_tool_events`):
```python
args = call_part.args
if isinstance(args, str):
    try:
        args = json.loads(args)
    except json.JSONDecodeError:
        args = {}
elif not isinstance(args, dict):
    args = {}

runtime.on_event(ToolCallEvent(
    worker=self.name,
    tool_name=call_part.tool_name,
    tool_call_id=call_id,
    args=args,
    depth=runtime.depth,
))
```
Proposed simplification (reuse `args_json` when available, reduce JSON parsing paths):
```python
args = call_part.args if isinstance(call_part.args, dict) else {}
args_json = call_part.args_as_json_str() if hasattr(call_part, "args_as_json_str") else ""

runtime.on_event(ToolCallEvent(
    worker=self.name,
    tool_name=call_part.tool_name,
    tool_call_id=call_id,
    args=args,
    args_json=args_json,
    depth=runtime.depth,
))
```
Judgment call: if JSON output consumers require a fully parsed dict even when only a JSON string is present, keep the `json.loads` path but move it into a shared helper (ideally in `llm_do/ui/parser.py`) so the event-stream and fallback paths stay consistent.
Inconsistency prevented: yes. The event-stream path populates `args_json`, but the fallback path does not, so the UI renders tool calls differently depending on how events were emitted.

### 5) Reduce over-specified `Invocable.call` signature (over-specified interface)
Current code (protocol and implementations):
```python
async def call(
    self,
    input_data: Any,
    config: RuntimeConfig,
    state: CallFrame,
    run_ctx: RunContext[WorkerRuntimeProtocol],
) -> Any: ...
```
Proposed simplification (single source of truth via `run_ctx.deps`):
```python
async def call(
    self,
    input_data: Any,
    run_ctx: RunContext[WorkerRuntimeProtocol],
) -> Any: ...
```
`Worker` and `ToolInvocable` can read `run_ctx.deps.config` / `run_ctx.deps.frame` directly.
Judgment call: this is a breaking interface change across `llm_do/runtime/deps.py`, `llm_do/runtime/contracts.py`, and any tests that mock `Invocable`.
Inconsistency prevented: potentially. Passing `config/state` separately from `run_ctx.deps` allows drift if the API evolves; removing them guarantees one source of truth.

### 6) Drop the `all_messages` compatibility shim if we can standardize (unused flexibility)
Current code:
```python
all_messages = getattr(result, "all_messages", None)
if callable(all_messages):
    return list(all_messages())
if all_messages is not None:
    return list(all_messages)
```
Proposed simplification:
```python
return list(result.all_messages())
```
Judgment call: confirm all result/stream objects expose `all_messages()` (or only a property). If multiple shapes exist for good reason, keep the shim but document the supported interface.
Inconsistency prevented: mild. Standardizing makes message collection behavior uniform.

## Open Questions
- Should compatibility checks apply to `Model` instances, and should nested workers enforce the `model` + `compatible_models` exclusivity rule?
- Is the interface change to `Invocable.call` acceptable, or do we want to preserve the current two-object API for clarity?
- Do we need parsed args in tool events, or is `args_json` enough for display/telemetry?
- Can we standardize on a single `all_messages()` API from PydanticAI results, or do we still need to support multiple shapes?

## Conclusion
The main simplifications center on consolidating model resolution, removing boolean flags in the internal API, and centralizing message history/event handling. Most changes reduce duplication and align nested worker behavior with entry-time behavior; the larger interface change is the only item that would require broad refactoring.
