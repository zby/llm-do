---
description: Removing private PydanticAI dependency for message capture
---

# Stabilize Message Capture Without Private _agent_graph

## Context
We previously relied on `pydantic_ai._agent_graph` in `llm_do/runtime/agent_runner.py` to capture messages incrementally for `message_log_callback`. That import reached into a private module and mutated `_RunMessages.messages` so we could log as messages were appended. The comment about stability risk was accurate: upstream changes to internal names or message capture flow would break this path.

This is also entangled with nested worker runs. `capture_run_messages()` reuses a context-var when already present. Our `_capture_message_log()` replaces the shared `.messages` list with a custom logger, but the replacement is not stacked/restored. That means a child worker can overwrite the parent's logger, and subsequent messages in the parent run are logged under the wrong worker/depth. In other words: the current implementation is brittle even before upstream changes.

## Findings
- Public API: `pydantic_ai.capture_run_messages()` is public, returns a plain `list` of messages for the first run in the context. There is no public access to the `_RunMessages` holder or context variable, and no supported way to intercept list mutation.
- Streaming API: `event_stream_handler` yields `PartStart/PartDelta/PartEnd` plus tool call/result events. These are public and stable, but they are **not** `ModelRequest`/`ModelResponse` objects.
- Current logging is inconsistent: with `message_log_callback` we attempt incremental logs, without it we log once at the end. Nested runs already compromise ordering and worker attribution during incremental logging.

## Recommended Approach
1) **Remove the private `_agent_graph` dependency and accept end-of-run message logging.**
   - Use only public `pydantic_ai.capture_run_messages()` (or just `result.all_messages()` as we already do) and call `runtime.log_messages()` once per run via `_finalize_messages`.
   - Keep `message_log_callback` but document that it emits a snapshot after the run completes, not incremental logs. This makes logging deterministic and avoids nested-run corruption.
   - This is the smallest, most stable change, and it fixes the incorrect worker attribution for nested runs.

2) **If incremental logs are still valuable, switch to an event-based log channel.**
   - Add a new callback (e.g. `event_log_callback`) that receives the raw PydanticAI events we already stream for UI.
   - Update `-vvv` (or introduce a new flag) to emit these events instead of serializing `ModelMessage` objects.
   - This avoids private imports and gives us true streaming without trying to reverse-engineer message objects.

3) **Only if we truly need incremental `ModelMessage` objects: build a local message accumulator.**
   - Use event stream events to construct `ModelResponse` parts and append them to a local list, then flush completed messages to the callback.
   - This is complex, will likely differ from PydanticAI’s internal message structure, and still won’t capture request messages faithfully unless we recreate them from inputs. It should be a last resort.

## Status (2026-02-01)
Implemented approach (1): removed incremental capture, so `message_log_callback`
now emits end-of-run snapshots and the private `_agent_graph` dependency is gone.

## Open Questions
- Do we still need incremental `message_log_callback` output, or is a post-run snapshot sufficient for CLI/debugging?
- Are we willing to change `-vvv` output format to events instead of serialized `ModelMessage` objects?
- If we keep event-based logs, should `message_log_callback` be replaced or renamed to avoid implying message-level objects?
