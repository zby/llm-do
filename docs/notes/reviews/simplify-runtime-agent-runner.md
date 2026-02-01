# Simplify runtime/agent_runner.py

## Context
Review of `llm_do/runtime/agent_runner.py` for simplification opportunities in the
PydanticAI agent execution flow.

## Findings

### 1) Drop incremental message capture (private API + nested-run risk)
- `_capture_message_log` reaches into `pydantic_ai._agent_graph`, mutating a
  private `_RunMessages` list to log incrementally.
- This creates brittleness (private API) and nested-run attribution bugs
  (child runs overwrite parent message lists).
- Simplify by removing `_MessageLogList` / `_capture_message_log` and always
  logging once via `_finalize_messages`. `message_log_callback` still receives a
  snapshot, just at end-of-run.
- Trade-off: `-vvv` JSONL output becomes end-of-run, not streaming. If streaming
  is still required, consider an event-based callback instead.

### 2) Collapse tool-event handling to a single source
- `_emit_tool_events` re-parses messages to synthesize ToolCall/ToolResult
  events, duplicating logic already in the event stream parser and losing
  `ToolCallEvent.args` (only `args_json` is set).
- Simplify by either:
  - Dropping the fallback entirely if `event_stream_handler` always emits tool
    events, or
  - Centralizing ToolCall/ToolResult construction so both paths share the same
    args/args_json behavior.
- Trade-off: removing the fallback delays tool events until run completion if
  the event stream is missing tool events. Confirm coverage in tests.

### 3) Trim redundant parameters/guards in run helpers
- `_build_agent` is only used in `run_agent`, and its `toolsets` argument always
  comes from `runtime.frame.config.active_toolsets`. Inline the construction or
  have `_build_agent` read from `runtime` directly.
- `_run_with_event_stream` and `_emit_tool_events` guard `runtime.config.on_event`
  even though they are only called when `on_event` is set. Removing those checks
  reduces branching and makes preconditions explicit.

## Open Questions
- Is it acceptable for `message_log_callback` (`-vvv`) to emit only end-of-run
  snapshots rather than incremental logs?
- Do any PydanticAI paths skip tool call/result events in the event stream,
  making `_emit_tool_events` necessary?
- Should `ToolCallEvent` keep both `args` and `args_json`, or can we standardize
  on one representation to avoid duplication?

## Conclusion
The largest simplification win is removing the incremental message-capture path
and its private API dependency. Next is collapsing tool-event handling to a
single source of truth. The remaining cleanups are small parameter/guard
reductions that make the run flow more direct.

## 2026-02-01 Review

- Incremental message capture still relies on private PydanticAI
  `_agent_graph` APIs. Removing `_MessageLogList` + `_capture_message_log`
  and always using `_finalize_messages` would simplify and avoid private
  dependency risk. Done: incremental capture removed; logging now uses
  end-of-run snapshots.
- `_build_agent()` is only used by `run_agent()`. Inline it to avoid a
  one-off helper that only forwards parameters.
- Tool-event fallback (`_emit_tool_events`) re-parses messages and can diverge
  from event-stream behavior. Either drop the fallback or centralize tool-event
  construction in one helper to remove duplicated logic and args handling.
  Done: fallback removed in favor of event stream only.
- `run_agent()` has two code paths (with/without `on_event`) that repeat
  message finalization and output extraction. A small helper that accepts an
  optional event handler could reduce branching.
