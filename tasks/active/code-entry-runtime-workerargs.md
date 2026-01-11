# Code Entry Runtime: WorkerArgs Input

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Code entries receive `Runtime` plus a normalized `WorkerArgs` input, and the runtime handles input normalization/prompt derivation centrally.

## Context
- Relevant files/symbols: `llm_do/runtime/shared.py` (`Runtime.run_invocable()`), `llm_do/runtime/worker.py` (`EntryFunction.call()`), `llm_do/runtime/args.py` (`WorkerArgs`, `ensure_worker_args()`), `llm_do/runtime/deps.py` (`WorkerRuntime.run()`), `llm_do/cli/main.py` (CLI input normalization)
- Related tasks/notes/docs: `docs/notes/code-entry-runtime-design.md` (removed per request; this task captures the decisions)
- How to verify / reproduce: run entry functions via CLI manifest and ensure code entries receive `WorkerArgs` while prompt logging behaves the same

## Decision Record
- Decision: Normalize entry inputs to `WorkerArgs` and pass that to code entry functions; entries receive `Runtime`, not `WorkerRuntime`
- Inputs: design discussion captured in removed note; manifest input is authoritative; entry path is trusted (no approval wrapper needed)
- Options: keep string/dict inputs; introduce schema selection; pass validated model to entry function
- Outcome: unify on `WorkerArgs` and let entries decode as needed
- Follow-ups: revisit event emission for entry tool calls if needed

## Tasks
- [ ] Update entry function contract to accept `(args: WorkerArgs, runtime: Runtime)`
- [ ] Normalize input to `WorkerArgs` inside `Runtime.run_invocable()`; set `CallFrame.prompt` from `prompt_spec()`
- [ ] Remove/adjust `WorkerRuntime.run()` usage for entry paths
- [ ] Update docstrings/examples/tests to match new signature
- [ ] Add/adjust tests that verify entry input normalization

## Current State
Task drafted; design note removed; no code changes yet.

## Notes
- Entry functions are a trusted path; tool calls can operate at depth 0 without approvals
