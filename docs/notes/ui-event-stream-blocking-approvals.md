---
description: Approval broker design for event-stream UI with blocking approvals
---

# Event-Stream UI with Blocking Approvals

## Context
We discussed making llm-do’s UI a client of an event stream (separating UI from the runtime), similar to how other tools structure their product. The key question is how to preserve **blocking approvals** (tool calls that must pause execution until the user decides) when the UI is no longer in-process.

## Findings
- A pure event stream is one-way; blocking approvals require a **return channel** from UI → runtime.
- llm-do already has the right abstraction for this: `ApprovalPolicy.approval_callback` (see `llm_do/runtime/approval.py`) is an awaitable “ask the user” function. Today, the Textual TUI wires it via in-process queues (see `llm_do/cli/main.py` and `llm_do/ui/app.py`).
- A networked “UI client” version can follow the same shape by introducing an **approval broker**:
  - Runtime generates an `approval_id` and emits an `approval_request` event containing:
    - `approval_id`, `tool_name`, `reason/description`, `args`, and an optional stable `cache_key`
  - Runtime awaits a Future keyed by `approval_id`.
  - UI renders the request and sends an `approval_response` back:
    - `approval_id`, `approved`, optional `remember` (e.g., `"session"`), optional `note`
  - Broker resolves the Future and returns an `ApprovalDecision` to the tool approval wrapper.
- Transport options:
  - **SSE/HTTP**: `GET /events` (SSE) for streaming events + `POST /approval/response` for responses.
  - **WebSocket**: single bidirectional channel for both event stream and approval responses.
- Session-level “remember” semantics remain server-side:
  - If decision has `remember="session"`, store it in a server-side cache keyed by a stable representation of `(tool_name, tool_args)` (see cache behavior in `llm_do/runtime/approval.py`).
- Approval payloads likely need **redaction/truncation** rules so tool args are safe and reasonably sized for UI transport and rendering.
- Approvals should be **idempotent** (keyed by `approval_id`) with explicit retry/duplicate handling to avoid double-approve and hanging Futures.
- The “remember” cache key needs **canonicalization** (stable serialization/ordering) to avoid flaky matching.
- Disconnection/timeout behavior needs a **default policy** so approvals do not block forever.

## Proposed In-Process Approval Broker (Draft)
Goal: preserve the existing `ApprovalPolicy.approval_callback` flow while making UI a pure event-stream client.

### Broker Interface
- `request_approval(request) -> Awaitable[ApprovalDecision]`: called by runtime; emits an approval event and awaits a response.
- `respond(approval_id, decision) -> None`: called by UI; resolves the pending approval (idempotent).
- `events() -> AsyncIterator[UIEvent]`: UI consumes an in-process event stream.

### Event Envelope (Versioned)
All UI events share:
- `type`: string, e.g. `"approval.requested"`, `"approval.resolved"`, `"approval.expired"`
- `version`: integer, start at `1`
- `run_id`: string
- `approval_id`: string
- `created_at`: unix epoch seconds (float) or monotonic timestamp
- `payload`: event-specific object

### Approval Request Payload (Minimal)
Emitted by broker on `request_approval`:
- `tool_name`: string
- `description`: string (human-readable reason)
- `safe_args`: object (redacted + truncated preview)
- `redactions`: object (summary of what was redacted/truncated)
- `cache_key`: string (server-generated, stable)
- `timeout_s`: integer (for UI display)

### Approval Response Payload (From UI)
Passed to `respond`:
- `approved`: bool
- `remember`: optional string (e.g. `"session"`)
- `note`: optional string

### Idempotency + Timeout
- First response wins; subsequent responses are ignored and logged.
- On timeout, broker resolves with a specific error (e.g. `ApprovalTimeout`) and emits `approval.expired`.
- UI can surface expiry; runtime surfaces the error for visibility.

### Redaction + Truncation (Denylist)
- Redact common secret keys by name match (case-insensitive), e.g. `api_key`, `apikey`, `token`, `secret`, `password`, `authorization`, `cookie`, `session`, `bearer`, `access_key`, `private_key`.
- Truncate long strings (e.g. 2k chars) and cap container sizes (e.g. 50 items).
- Allow tools to provide `display_args` or equivalent to bypass guessy redaction when needed.

### Cache Key Canonicalization
- Compute `cache_key` server-side from full tool args, using canonical JSON (sorted keys, stable formatting) and hash (e.g. sha256).
- Cache key should not depend on redacted preview to avoid mismatches.

## Open Questions
- Routing: how to scope approvals to a run/session if multiple concurrent runs exist.
- Reliability: should UI reconnect re-emit pending approvals or just read current state.
- Security: local-only binding vs auth token; preventing arbitrary approval injection (if/when remote UI exists).
- Persistence: do we store approval decisions beyond a single run/session (probably no, unless explicitly configured).
- Redaction details: finalize key denylist, truncation thresholds, and container caps.

## Conclusion
Decision: keep the event stream and approvals in-process for now; defer any network transport. If we revisit remote UI later, start by factoring the current in-process approval queue into a reusable "approval broker" interface so both Textual (local) and a future remote UI can share the same `ApprovalPolicy.approval_callback` wiring. Initial defaults: timeout raises an error for visibility; single UI controller; denylist + truncation redaction for `args`.

---

Relevant Notes:
- [[approvals-guard-against-llm-mistakes-not-active-attacks]] — grounds: the broker's timeout, redaction, and "remember" design treats approvals as UX affordances, which follows from approvals being error-catching rather than security gates
- [[capability-based-approvals]] — implements: the broker's cache_key, remember semantics, and timeout behavior are the runtime mechanism for capability grant lifetime described in the capability-based design
- [[we-want-to-get-rid-of-approval-wrapping]] — adapts: when wrapping is eliminated, the broker's `request_approval` / `respond` interface adapts to produce `DeferredToolResult` (Path 1) or integrate with `before_tool_call` hooks (Path 2)
