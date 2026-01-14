# Entry Tool Plane Parity (Approvals + Event Attribution)

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Entry functions run through the same tool plane as workers (approval wrapping on `ctx.call()`), and tool events are attributed to the invoking entry/worker instead of a generic label.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/shared.py` (`Runtime.run_entry`)
  - `llm_do/runtime/worker.py` (`Worker._call_internal`, `spawn_child`)
  - `llm_do/runtime/deps.py` (`WorkerRuntime.call`, `WorkerRuntime.spawn_child`)
  - `llm_do/runtime/approval.py` (`wrap_toolsets_for_approval`, `RunApprovalPolicy`)
  - `llm_do/ui/events.py` (tool event payloads)
- Related tasks/notes/docs:
  - `docs/notes/unified-entry-function-design.md`
- How to verify / reproduce:
  - Add/adjust a runtime test that invokes an entry function calling a tool and asserts tool events carry the entry name.
  - Add/adjust a runtime test that worker tool events carry the worker name (no `code_entry`).

## Decision Record
- Decision: Entry functions stay in the tool plane; approvals are governed by runtime `RunApprovalPolicy` with no per-call bypass.
- Inputs: `docs/notes/unified-entry-function-design.md` (tool-plane parity, event attribution).
- Options:
  - Keep `code_entry` label in tool events for entry calls.
  - Attribute tool events to the invoking entry/worker name.
- Outcome: Attribute tool events by invocation owner; entry tool calls are approval-wrapped like worker tool calls.
- Follow-ups:
  - Extract a shared tool-plane builder once parity is enforced (separate task).

## Tasks
- [ ] Add an `invocation_name` (or similar) to `WorkerRuntime` and use it for tool event attribution in `WorkerRuntime.call`.
- [ ] Update `Runtime.run_entry` to set the invocation name to the entry name and to wrap entry toolsets using `wrap_toolsets_for_approval`.
- [ ] Ensure worker invocations set the invocation name to the worker name on the child runtime in `Worker._call_internal`.
- [ ] Add/update tests for entry/worker tool event attribution and entry approval wrapping.

## Current State
Task created; no code changes yet.

## Notes
- Keep depth semantics unchanged (CallFrame stack depth: entry=0, worker=1).
- Do not extract the shared environment builder in this task.
