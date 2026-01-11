# Simplify runtime/worker.py

## Context
Review of `llm_do/runtime/worker.py` for simplification opportunities in the worker runtime path.

## Findings

### 1) Drop unused bulk_approve plumbing on WorkerToolset (unused flexibility)
- `WorkerToolset.bulk_approve` is never read; `_call_internal` only checks `Worker.bulk_approve_toolsets`.
- `Worker.as_toolset(bulk_approve=...)` and `toolsets.loader._wrap_worker_as_toolset` pass it through, but it has no effect.
- Simplify by removing the field/parameter and wiring `bulk_approve_toolsets` solely at the worker level (or make the override real instead of dead).

### 2) Consolidate tool-call event parsing for fallback (duplicated derived values)
- `_emit_tool_events` manually parses `ToolCallPart.args` and drops `args_json`.
- `llm_do/ui/parser.parse_event` already handles `args_as_json_str`, so the fallback path diverges from the event-stream path.
- Centralize ToolCallEvent/ToolResultEvent construction (helper in `llm_do/ui/parser.py` or a shared helper here) and reuse it in `_emit_tool_events`.

### 3) Fold message-history syncing into the run helpers (duplicated logic)
- `_run_streaming`/`_run_with_event_stream` call `_finalize_messages` with `state=None`, then `_call_internal` re-syncs `state.messages` in the event path.
- Allow the run helpers to accept an optional `state` or pass it into `_finalize_messages` to keep message logging and history sync in one place.

## Open Questions
- Do we want to support per-toolset bulk-approve overrides, or should `Worker.bulk_approve_toolsets` be the only control?
- Should fallback tool-call events keep parsed args, or is a JSON string enough for display/logging?

## Conclusion
Most earlier simplifications are already in place. The remaining cleanup is mostly removing unused flags and consolidating tool-event/message-history handling to reduce duplicated logic.
