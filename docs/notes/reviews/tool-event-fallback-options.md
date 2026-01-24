# Tool Event Fallback Options

## Context
`llm_do/runtime/agent_runner.py` emits tool call/result events via two paths:
1) Streaming `event_stream_handler` → `parse_event(...)`
2) Post-run fallback `_emit_tool_events(...)` which re-parses
   `result.new_messages()` if the stream emitted no tool events.

This creates duplicated logic and inconsistent `ToolCallEvent` payloads
(`args` vs `args_json`). We want to simplify but are postponing changes.

## Findings

### Option 1: Keep fallback, consolidate event construction (minimal change)
- Add shared helpers for ToolCallEvent/ToolResultEvent creation
  (likely in `llm_do/runtime/event_parser.py`).
- Use helpers from both `parse_event(...)` and `_emit_tool_events(...)`.
- Pros: low risk, keeps current behavior.
- Cons: still two sources; fallback is “all or nothing” and can’t fill partial
  gaps if stream emits only calls or only results.

### Option 2: Reconcile missing events (more robust)
- Track tool call/result IDs seen in the stream.
- After run, parse `result.new_messages()` and emit only missing events.
- Pros: handles partial stream gaps; still supports streaming UX.
- Cons: more bookkeeping; “missing” events are end-of-run in the UI.

### Option 3: Remove fallback entirely (simplest code)
- Trust stream events and delete `_emit_tool_events`.
- Pros: cleanest flow, one source of truth.
- Cons: if stream ever omits tool events, UI loses them.

### Option 4: Use only post-run messages for tool events (deterministic)
- Ignore stream tool events; emit tool events only after completion.
- Pros: single deterministic source.
- Cons: tool calls/results no longer stream live in UI.

## Open Questions
- Are streaming tool events required for UX, or is end-of-run acceptable?
- Do we expect partial stream gaps (calls without results)? If yes, Option 2
  provides the most robust behavior.
- Should we standardize on `args_json` and treat `args` as optional to avoid
  duplication?
