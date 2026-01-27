---
description: Analysis of runtime and UI event types, their meanings, emission points, and candidates for simplification
---

# Runtime + UI Events Analysis

## Summary
The runtime event stream now carries raw PydanticAI `AgentStreamEvent` values (plus a small set of llm-do system events) wrapped in a `RuntimeEvent` envelope with `worker` and `depth`. The UI layer projects these raw events into `UIEvent` types for rendering. This keeps us aligned with PydanticAI but also means some llm-do system events are currently defined but not emitted. The analysis below enumerates each event, where it is emitted, who consumes it, and which ones are likely redundant or candidates for removal.

## Current Event Flow
```
PydanticAI stream events + system events
        |
        v
RuntimeEvent(worker, depth, event)
        |
        v
adapt_event(RuntimeEvent) -> UIEvent (optional)
        |
        v
DisplayBackend / TUI widgets
```

Notes:
- Runtime no longer parses or re-shapes PydanticAI events; it forwards them as-is.
- UI filters `PartDeltaEvent` when verbosity < 2.

## Runtime Events
`RuntimeEvent` is an envelope: `{ worker, depth, event }` where `event` is either:
- A PydanticAI `AgentStreamEvent` (raw), or
- A llm-do system event (currently only `UserMessageEvent`).

### System Events
As of 2026-01-27, runtime defines only one system event: `UserMessageEvent`.

| Event | Meaning | Emitted by | Consumed by | Status |
| --- | --- | --- | --- | --- |
| `UserMessageEvent` | User input submitted | `Runtime.run_entry()` | UI adapter -> `UserMessageEvent` UI | **Emitted** |
System events such as `InitialRequestEvent`, `StatusEvent`, `DeferredToolEvent`, and `ErrorEvent` were removed to keep the runtime surface minimal; UI-owned error reporting remains in `ui/runner.py`.

### PydanticAI AgentStreamEvent
Raw events are forwarded unchanged. The UI adapter translates only a subset:

- `PartStartEvent` with `TextPart` -> `UI TextResponseEvent(is_complete=False)`
- `PartDeltaEvent` with `TextPartDelta` -> `UI TextResponseEvent(is_delta=True, content=delta)`
- `PartEndEvent` with `TextPart` -> `UI TextResponseEvent(is_complete=True, content=full)`
- `FunctionToolCallEvent` / `BuiltinToolCallEvent` -> `UI ToolCallEvent`
- `FunctionToolResultEvent` / `BuiltinToolResultEvent` -> `UI ToolResultEvent`
- `FinalResultEvent` -> `UI CompletionEvent`

Events not mapped today:
- Non-text parts (thinking, tool-call parts in the part stream, files) are ignored.
- `PartStartEvent` for non-text parts is ignored.

Fallback behavior:
- If no tool call/result events arrive via the stream, `_emit_tool_events()` synthesizes `FunctionToolCallEvent`/`FunctionToolResultEvent` from message history and emits them via `RuntimeEvent`. This is a duplication path intended to preserve tool observability.

## UI Events
UI events live in `llm_do/ui/events.py` and are the display-oriented projection layer.

| UI Event | Origin | Notes |
| --- | --- | --- |
| `InitialRequestEvent` | UI-only (not emitted by runtime) | Renders “Starting...” details |
| `StatusEvent` | UI-only (not emitted by runtime) | Renders phase/state/model |
| `UserMessageEvent` | System event (emitted) | Renders user prompt line |
| `TextResponseEvent` | PydanticAI PartStart/Delta/End (text only) | Drives streaming UI logic |
| `ToolCallEvent` | PydanticAI tool call events | Displays name + args |
| `ToolResultEvent` | PydanticAI tool result events | Displays result + error flag |
| `DeferredToolEvent` | UI-only (not emitted by runtime) | Placeholder for async tool updates |
| `CompletionEvent` | PydanticAI `FinalResultEvent` | UI-only; no runtime completion signal |
| `ErrorEvent` | UI runner error handling | Emitted by UI runner on exceptions |
| `ApprovalRequestEvent` | `parse_approval_request` | UI-only for approval prompts |

Important behavioral detail:
- Verbosity filtering happens in `ui/runner.py`, not in the runtime. External `on_event` callbacks will still see all deltas.

## Current Consumers
- **UI runner / headless backends**: expect `RuntimeEvent` and call `adapt_event()`.
- **External callbacks (tests/examples)**: tend to look for tool call/result events. After the alignment change, they now check `event.event` for PydanticAI types.
- **Textual UI**: relies on `TextResponseEvent` for streaming and `ToolCallEvent`/`ToolResultEvent` for tool panels.

## Redundancies / Gaps
1) **System events kept minimal**
   - Only `UserMessageEvent` remains in runtime. Additional system events can be reintroduced if/when needed.

2) **Completion vs FinalResult**
   - Runtime never emits a completion event. UI creates `CompletionEvent` from `FinalResultEvent`.
   - We can drop `CompletionEvent` if UI doesn’t need a distinct completion signal, or keep it as UI-only.

3) **Tool event duplication**
   - `_emit_tool_events` re-parses messages to emit tool events if streaming lacks them. This duplicates data and could be dropped if PydanticAI guarantees tool events in stream.

4) **Partial part coverage**
   - PydanticAI part events for tool-call parts, thinking parts, or file parts are ignored in UI. If we care about them, add UI events; if not, confirm intentional ignore.

5) **Error surface split**
   - UI runner emits UI `ErrorEvent` directly. Runtime-level error emission could be added later if desired.

## Simplification Options

### Option A: Minimal system events (implemented)
Keep only:
- `RuntimeEvent` envelope
- `UserMessageEvent`

UI still handles:
- `ErrorEvent` via runner
- `CompletionEvent` via `FinalResultEvent`
- `ApprovalRequestEvent` via approval flow

### Option B: Keep system events but start emitting them
If we want richer UI signals, we should emit:
- `InitialRequestEvent` at entry start
- `StatusEvent` during model/tool lifecycle (not currently instrumented)
- `DeferredToolEvent` when/if async tools exist
- `ErrorEvent` from runtime for unified error handling

### Option C: Remove tool-event fallback
If we trust PydanticAI’s stream to always include tool call/result events, we can delete `_emit_tool_events`. This reduces duplication and keeps the runtime purely stream-driven.

## Open Questions
- Do we actually need any system events besides `UserMessageEvent` right now?
- Should runtime be the canonical source of error events, or is UI-owned error emission sufficient?
- Do we want a UI-level `CompletionEvent`, or should UI rely on `FinalResultEvent` directly?
- Is the tool-event fallback still necessary, or can we rely on PydanticAI stream guarantees?
- Should UI start handling non-text parts (thinking, file, tool-call parts), or do we explicitly ignore them?
- If we keep `StatusEvent`, what lifecycle milestones should emit it and in which layer?
