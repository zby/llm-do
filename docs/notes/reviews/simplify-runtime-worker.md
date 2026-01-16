# Simplify runtime/worker.py

## Context
Review of `llm_do/runtime/worker.py` for simplification opportunities in the worker runtime path.

## Findings

### 1) Drop unused bulk_approve plumbing on WorkerToolset (resolved)
- Removed `WorkerToolset.bulk_approve`, `Worker.bulk_approve_toolsets`, and the scoped approval callback; approvals now rely on session cache/`--approve-all`.

### 2) Consolidate tool-call event parsing for fallback (duplicated derived values)
- `_emit_tool_events` manually parses `ToolCallPart.args` and drops `args_json`.
- `llm_do/ui/parser.parse_event` already handles `args_as_json_str`, so the fallback path diverges from the event-stream path.
- Centralize ToolCallEvent/ToolResultEvent construction (helper in `llm_do/ui/parser.py` or a shared helper here) and reuse it in `_emit_tool_events`.

### 3) Fold message-history syncing into the run helpers (duplicated logic)
- `_run_streaming`/`_run_with_event_stream` call `_finalize_messages` with `state=None`, then `_call_internal` re-syncs `state.messages` in the event path.
- Allow the run helpers to accept an optional `state` or pass it into `_finalize_messages` to keep message logging and history sync in one place.

### 4) Remove redundant config/state plumbing in `_call_internal` (over-specified interface)
- `_call_internal` always receives `run_ctx.deps.config` and `run_ctx.deps.frame`, so `config`/`state` arguments are derived values that can drift.
- Derive both from `run_ctx.deps` inside `_call_internal` and slim down `Worker.call`/`WorkerToolset.call_tool` signatures.

### 5) Avoid double path normalization for attachments (duplicated derived values)
- `_resolve_attachment_path` expands/resolves, then `AttachmentToolset.read_attachment` expands/resolves again.
- Choose a single normalization point (teach the toolset about `project_root` or accept already-resolved paths) to reduce duplicate work.

## Open Questions
- ~~Should fallback tool-call events keep parsed args, or is a JSON string enough for display/logging?~~ **Resolved**: Simplified to use `args_as_json_str()` directly, matching the event-stream path. Removed JSON parsing overhead.
- Where should `project_root`-relative attachment resolution live: `Worker` or `AttachmentToolset`?

## Conclusion
Most earlier simplifications are already in place. Remaining cleanup is consolidating tool-event/message-history handling, trimming `_call_internal` plumbing, and picking a single attachment path normalization path.
