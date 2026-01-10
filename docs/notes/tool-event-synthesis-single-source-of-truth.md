# Tool Event Synthesis and Single Source of Truth

## Context
Tool call events can be emitted two ways:
1) event-stream parsing (`llm_do/ui/parser.py`) from raw pydantic-ai events, and
2) message-based fallback synthesis (`llm_do/runtime/worker.py`) from `new_messages()`.

This dual-path design is meant to ensure tool calls appear in the UI even when
the event stream does not emit tool events. However, the two paths normalize
tool arguments differently, and only the event-stream path populates `args_json`.
This breaks the single source of truth rule for tool call data and causes the UI
and JSONL outputs to differ depending on which path is used.

## Findings

### Dual sources of truth
- Event-stream path: `parse_event()` builds `ToolCallEvent` with
  `args=tool_part.args` and `args_json=tool_part.args_as_json_str()`.
- Fallback path: `_emit_tool_events()` attempts `json.loads()` on strings,
  coerces non-dicts to `{}`, and does not set `args_json`.
- Code-entry path: `WorkerRuntime.call()` emits `ToolCallEvent` with dict args
  and also does not set `args_json`.

Net effect: the same logical tool call can surface as a dict or a JSON string,
with or without `args_json`, depending on the execution path.

### Divergent normalization behavior
- Event-stream keeps raw `args` as-is (string or dict).
- Fallback path rewrites string args into dicts, losing the original JSON
  serialization (ordering, whitespace, exact formatting).
- Fallback handles JSON errors by returning `{}`; event-stream preserves the
  raw string even if invalid JSON.
- pydantic-ai already exposes `args_as_dict()` and `args_as_json_str()`, but the
  fallback path re-implements parsing with different behavior.

### UI and JSONL inconsistencies
- UI rendering prefers `args_json` when present; fallback events never set it,
  so the same tool call renders differently across runs.
- JSONL output only includes `args`, so tooling that consumes JSONL must branch
  on whether `args` is a dict or a string.

### Why the fallback exists (and why it persists)
- Some runs do not emit tool call events (streaming mode only emits text deltas,
  providers vary in event support, and filtering may suppress tool parts).
- The fallback is a resiliency layer to avoid "missing tool calls" in the UI,
  but it introduces a second source of truth for the same data.

### Single source of truth violation
There is no canonical representation of tool call arguments. The system treats
event stream payloads and message history as independent sources, with
inconsistent normalization and loss of information. This creates non-determinism
in logs, UI output, and JSONL records, and makes debugging harder because two
paths can disagree about the same tool call.

## Design options and tradeoffs

### 1) Shared normalization helper (least disruptive)
Create a helper (likely in `llm_do/ui/parser.py`) that yields a normalized
`args` dict and `args_json` string using pydantic-ai helpers:
- Use `BaseToolCallPart.args_as_dict()` for parsed dicts when possible.
- Use `BaseToolCallPart.args_as_json_str()` for the canonical JSON string.
- Apply the same helper in both `parse_event()` and `_emit_tool_events()`,
  and optionally in `WorkerRuntime.call()`.

Pros: consistent output with minimal behavior changes.
Cons: still two sources, but at least the normalization is shared.

### 2) Messages as the single source of truth
Always derive tool events from `new_messages()` and ignore stream tool events.

Pros: one canonical path, easier reasoning.
Cons: tool calls can only appear after a run completes, reducing live feedback.

### 3) Event stream as the single source of truth
Require stream events for tool calls; treat missing tool events as an error or
explicit warning.

Pros: true streaming tool visibility, canonical path.
Cons: brittle across providers and likely to regress current behavior.

### 4) Expand ToolCallEvent to always carry raw + normalized args
Store both forms in the event and standardize downstream rendering and JSONL.

Pros: preserves information and lets consumers choose.
Cons: schema change; must decide on backward compatibility strategy.

### 5) Normalize inside ToolCallEvent instead of at call sites
Accept raw args and normalize lazily in `render_*` or constructor.

Pros: fewer call sites, consistent formatting.
Cons: hidden side effects and unclear error handling location.

## Open Questions
- Which representation should be canonical: raw JSON string or parsed dict?
- Do we want tool call output to be readable (pretty dict) or canonical
  (compact JSON) in the UI?
- Should JSONL include `args_json` in addition to `args` for automation?
- Is "tool calls after completion only" acceptable if we prefer a single source?
- Should code-entry tool calls (`WorkerRuntime.call()`) be normalized the same
  way as LLM-driven calls?
- What should happen when args are invalid JSON strings: preserve or coerce?

## Conclusion
The current tool-event design creates two independent sources for tool call
data and violates the single source of truth rule. The most practical fix is to
centralize argument normalization and use it in all tool-event emission paths,
ensuring consistent UI and JSONL output while preserving the fallback behavior.
If a stricter single-source approach is required, we must explicitly choose
either stream events or message history as the canonical source, and accept the
UX consequences.
