# Run Entry Approval Boundary

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Introduce a single `run_entry(...)` boundary that applies approval wrapping via a helper and centralizes execution-time policy.

## Context
- Relevant files/symbols: `llm_do/ctx_runtime/cli.py`, `llm_do/ctx_runtime`, `ApprovalToolset`, `WorkerRuntime`
- Related tasks/notes/docs: `docs/notes/workerruntime-and-approval-design.md`
- How to verify / reproduce: `uv run ruff check .`, `uv run mypy llm_do`, `uv run pytest`

## Decision Record
- Decision: Add `run_entry(...)` and `wrap_entry_for_approval(...)`; keep `ApprovalToolset`; require explicit `ApprovalPolicy`.
- Inputs: `docs/notes/workerruntime-and-approval-design.md`
- Options: helper vs runtime vs compile pipeline; persistent cache vs per-run; ToolContext vs `WorkerRuntime`
- Outcome: helper + `run_entry(...)`, per-run cache only, keep `WorkerRuntime` in `RunContext`, no pre-wrapped toolsets.
- Follow-ups: Revisit ToolContext and wrapper pipeline only if a concrete use-case emerges.

## Tasks
- [ ] Add `wrap_entry_for_approval(...)` helper that mirrors current recursive wrapping behavior.
- [ ] Add `run_entry(...)` as the single execution boundary and require explicit `ApprovalPolicy`.
- [ ] Update CLI to call `run_entry(...)` (remove bespoke wrapping logic).
- [ ] Update programmatic entry points/docs/examples to use `run_entry(...)`.
- [ ] Add/update tests covering approvals and run boundary behavior.
- [ ] Run lint/typecheck/tests.

## Current State
Design decisions locked; task created and ready for implementation.

## Notes
- Avoid pre-wrapped toolsets; keep wrapping explicit in the run boundary.
