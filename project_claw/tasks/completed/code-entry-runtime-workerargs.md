# Code Entry Runtime: WorkerArgs Input

## Status
completed

## Prerequisites
- [x] none

## Goal
Code entries receive `Runtime` plus a normalized `WorkerArgs` input, and the runtime handles input normalization/prompt derivation centrally.

## Context
- Relevant files/symbols: `llm_do/runtime/shared.py` (`Runtime.run_invocable()`), `llm_do/runtime/worker.py` (`EntryFunction.call()`), `llm_do/runtime/args.py` (`WorkerArgs`, `ensure_worker_args()`), `llm_do/runtime/deps.py` (`WorkerRuntime.run()`), `llm_do/cli/main.py` (CLI input normalization)
- Related tasks/notes/docs: `docs/notes/code-entry-runtime-design.md` (removed per request; this task captures the decisions)
- How to verify / reproduce: run entry functions via CLI manifest and ensure code entries receive `WorkerArgs` while prompt logging behaves the same

## Decision Record
- Decision: Normalize entry inputs to `WorkerArgs` and pass that to code entry functions; entries receive `WorkerRuntime` (which provides tool access via `.call()`)
- Inputs: design discussion captured in removed note; manifest input is authoritative; entry path is trusted (no approval wrapper needed)
- Options: keep string/dict inputs; introduce schema selection; pass validated model to entry function
- Outcome: unify on `WorkerArgs` and let entries decode as needed
- Follow-ups: revisit event emission for entry tool calls if needed

## Tasks
- [x] Update entry function contract to accept `(args: WorkerArgs, runtime: WorkerRuntime)`
- [x] Normalize input to `WorkerArgs` inside `Runtime.run_invocable()`; set `CallFrame.prompt` from `prompt_spec()`
- [x] Remove/adjust `WorkerRuntime.run()` usage for entry paths (EntryFunction now called directly from `run_invocable()`)
- [x] Update docstrings/examples/tests to match new signature
- [x] Add/adjust tests that verify entry input normalization

## Current State
Implementation complete. All 322 tests pass.

## Implementation Summary
1. `Runtime.run_invocable()` now normalizes all inputs to `WorkerArgs` using `ensure_worker_args()`, sets `frame.prompt` from `prompt_spec()`, and directly calls `EntryFunction.call()` bypassing `WorkerRuntime.run()`
2. `EntryFunction.call()` signature changed from `(input_data: Any, run_ctx: RunContext)` to `(input_args: WorkerArgs, runtime: WorkerRuntimeProtocol)`
3. User-defined `@entry` functions now receive `(args: WorkerArgs, runtime: WorkerRuntime)` instead of `(input: str, ctx: WorkerRuntime)`
4. Updated `Entry` protocol documentation to note the different call signatures for Worker vs EntryFunction
5. Updated example `pitchdeck_eval_code_entry/tools.py` and documentation

## Notes
- Entry functions are a trusted path; tool calls can operate at depth 0 without approvals
- Entry functions receive `WorkerRuntime` (not `Runtime`) to maintain tool calling ability via `runtime.call()`
