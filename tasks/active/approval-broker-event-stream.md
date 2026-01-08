# Approval Broker for In-Process Event-Stream UI

## Status
ready for implementation

## Prerequisites
- [ ] design decision needed (approval broker semantics and UI payloads)

## Goal
Define the in-process approval broker interface and approval event payloads, including redaction, idempotency, timeout, and ownership semantics.

## Context
- Relevant files/symbols: `llm_do/runtime/approval.py`, `llm_do/ui/app.py`, `llm_do/cli/main.py`
- Related tasks/notes/docs: `docs/notes/ui-event-stream-blocking-approvals.md`
- How to verify / reproduce: review the protocol write-up and confirm it covers the failure modes in the note
- Motivation: future remote UI work risks stalled runs, duplicate approvals, and data leakage without a clear protocol; documenting the minimum viable semantics now reduces rework and makes the eventual implementation safer.

## Decision Record
- Decision: keep approvals in-process for now; no network transport
- Inputs: existing approval callback contract; note on event-stream UI and blocking approvals
- Options: in-process event stream vs remote transport
- Outcome: in-process event stream
- Follow-ups: document the broker interface, event payloads, and lifecycle; update the note with final decisions
- Decision: timeouts raise errors for visibility during development (may switch to auto-deny later)
- Decision: single UI controller for now
- Decision: redaction uses denylist + truncation for tool args

## Tasks
- [ ] Define in-process approval broker interface and event channel shape
- [ ] Define approval request/response payload fields used by the UI
- [ ] Specify redaction/truncation policy for tool args
- [ ] Define idempotency, retry, and timeout behavior
- [ ] Decide ownership rules for multi-client approvals (if applicable)
- [ ] Update docs/notes with final decisions and rationale

## Current State
Task created from the event-stream approvals note; in-process decision recorded and basic defaults chosen; draft interface/payload spec added to the note but not yet turned into code.

## Notes
- Keep the note concise; move detailed rationale here if it grows.
