# Entry Tool Plane Parity (Approvals + Event Attribution)

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Entry functions run through the same tool plane as workers (approval wrapping on `ctx.call()`), and tool events are attributed to the invoking entry/worker via a propagated invocation name.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/shared.py` (`Runtime.run_entry`)
  - `llm_do/runtime/worker.py` (`Worker._call_internal`, `spawn_child`)
  - `llm_do/runtime/deps.py` (`WorkerRuntime.call`, `WorkerRuntime.spawn_child`)
  - `llm_do/runtime/approval.py` (`wrap_toolsets_for_approval`, `RunApprovalPolicy`)
  - `llm_do/ui/events.py` (tool event payloads)
  - `tests/runtime/helpers.py` (`build_runtime_context`)
  - Comments to update: `llm_do/runtime/shared.py`, `llm_do/runtime/deps.py`, `llm_do/runtime/approval.py`
- Related tasks/notes/docs:
  - `docs/notes/unified-entry-function-design.md`
- How to verify / reproduce:
  - Update the entry attribution test in `tests/runtime/test_events.py` to expect entry name (no `code_entry`).
  - Add/adjust an approval test to confirm entry tool calls respect `return_permission_errors` (parity with workers).

## Decision Record
- Decision: Entry functions stay in the tool plane; approvals are governed by runtime `RunApprovalPolicy` with no per-call bypass.
- Decision: Invocation name is per-call state and must propagate through `spawn_child` with optional override.
- Inputs: `docs/notes/unified-entry-function-design.md` (tool-plane parity, event attribution).
- Options:
  - Keep `code_entry` label in tool events for entry calls.
  - Attribute tool events to the invoking entry/worker name.
  - Store invocation name on `WorkerRuntime` only (manual propagation).
  - Store invocation name on `CallFrame`/`CallConfig` (automatic propagation) with explicit override for worker calls.
- Outcome: Attribute tool events by invocation owner; entry tool calls are approval-wrapped like worker tool calls; store invocation name with per-call state.
- Follow-ups:
  - Extract a shared tool-plane builder once parity is enforced (separate task).

## Tasks
- [ ] Add `invocation_name` to per-call state (CallFrame/CallConfig) and plumb through `WorkerRuntime`; default propagation in `spawn_child`, with override support for worker invocations.
- [ ] Update `Runtime.run_entry` to set invocation name to the entry name and wrap entry toolsets with `wrap_toolsets_for_approval` using `return_permission_errors`.
- [ ] Update `Worker._call_internal` to set invocation name to the worker name for child runtimes, including attachment reads.
- [ ] Replace `code_entry` labeling in `WorkerRuntime.call` with invocation name; ensure missing names fall back to entry/worker name defaults.
- [ ] Update tests (`tests/runtime/test_events.py`, `tests/runtime/helpers.py`) and fix docstrings/comments in runtime files that still claim entry calls bypass approvals.

## Current State
Task created; no code changes yet.

## Notes
- Keep depth semantics unchanged (CallFrame stack depth: entry=0, worker=1).
- Do not extract the shared environment builder in this task.
