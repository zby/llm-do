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
- ApprovalPolicy spec:
  - Location: `llm_do/ctx_runtime/approval_wrappers.py` (export from `llm_do/ctx_runtime/__init__.py`).
  - Fields: `mode` (`prompt` | `approve_all` | `reject_all`), `approval_callback` (optional), `return_permission_errors`, `cache` (per-run dict or None), `cache_key_fn` (optional).
  - Mapping: CLI `--approve-all` → `mode="approve_all"`; `--reject-all` → `mode="reject_all"`; default → `mode="prompt"`.
  - Headless: `run_entry(...)` uses `make_headless_approval_callback(...)` when `approval_callback` is None.
  - TUI: `run_entry(...)` wraps `approval_callback` with `make_tui_approval_callback(...)` using per-run cache.
- run_entry API/placement:
  - Location: `llm_do/ctx_runtime/runner.py` (new module).
  - Signature: `async def run_entry(entry: Invocable, prompt: str, *, model: str | None, approval_policy: ApprovalPolicy, on_event: EventCallback | None, verbosity: int, message_history: list[Any] | None) -> tuple[Any, WorkerRuntime]`.
  - Ownership: `cli.run(...)` becomes a thin wrapper that builds the entry from files and calls `run_entry(...)`. TUI/headless flows also call `run_entry(...)`.

## Call Sites to Update
- `llm_do/ctx_runtime/cli.py:run` → thin wrapper over `run_entry(...)`.
- `llm_do/ctx_runtime/cli.py:_run_tui_mode` → build `ApprovalPolicy` with TUI callback, call `run_entry(...)`.
- `llm_do/ctx_runtime/cli.py:_run_headless_mode` → build `ApprovalPolicy` with headless mode, call `run_entry(...)`.
- Docs/examples: search `rg -n \"ctx_runtime\\.cli import run|build_entry\\(\" docs examples` and update any direct usage to `run_entry(...)`.

## Tasks
- [ ] Define `ApprovalPolicy` (schema + mapping from CLI flags) and export it.
- [ ] Add `wrap_entry_for_approval(...)` helper that mirrors current recursive wrapping behavior.
- [ ] Add `run_entry(...)` as the single execution boundary and require explicit `ApprovalPolicy`.
- [ ] Update CLI to call `run_entry(...)` (remove bespoke wrapping logic in `cli.run` and TUI/headless flows).
- [ ] Update programmatic entry points/docs/examples to use `run_entry(...)` (see Call Sites to Update).
- [ ] Add/update tests covering approvals and run boundary behavior.
- [ ] Run lint/typecheck/tests.

## Current State
Design decisions locked; task created and ready for implementation.

## Notes
- Avoid pre-wrapped toolsets; keep wrapping explicit in the run boundary.
