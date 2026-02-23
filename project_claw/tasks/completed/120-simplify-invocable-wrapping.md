# Simplify Invocable Wrapping

## Status
completed

## Prerequisites
- [x] decide per-worker approval config source (per-tool config in .worker; merged with CLI run policy; no inheritance from parent)
- [x] decide assembly hook (wrap toolsets at agent creation in Worker.call)
- [x] decide pre-wrapped toolset handling (tests/live helper vs supported API)
- [x] decide whether pre_approved can bypass blocked decisions (shell)

## Goal
Move approval wrapping to agent creation in Worker.call so that:
- each worker wraps its own toolsets when building its Agent (no recursive wrap/unwrap)
- nested worker calls use their own .worker approval config (no inheritance) and are still approval-gated
- ToolInvocable entry calls remain un-gated by approvals (current behavior)
- per-worker `_approval_config` behavior is preserved
- tests and docs reflect the new assembly flow

## Context
- Relevant files/symbols:
  - `llm_do/runtime/approval.py` (`RunApprovalPolicy`, `WorkerApprovalPolicy`, `wrap_entry_for_approval`)
  - `llm_do/runtime/worker.py` (`Worker.toolsets`, `ToolInvocable`)
  - `llm_do/toolsets/loader.py` (`ToolsetRef`, toolset resolution)
  - `llm_do/cli/main.py` (toolset assembly for workers and entries)
  - `llm_do/runtime/runner.py` (run boundary and approval policy)
  - `llm_do/runtime/context.py` (execution and tool dispatch)
- Related tasks/notes/docs:
  - `docs/notes/per-worker-approval-config.md`
  - `docs/architecture.md` (approval/toolset flow)
- How to verify / reproduce:
  - `uv run pytest tests/runtime/test_approval_wrappers.py`
  - Update/add tests: `tests/runtime/test_approval_wrapping.py` (no recursive wrap/unwrap, cycles),
    a nested-worker approval test, a ToolInvocable entry test (entry calls remain un-gated),
    and a repeat-run test to confirm ApprovalPolicy does not leak across runs.
  - Update `tests/live/conftest.py` helper if pre-wrapped toolsets are removed.

## Decision Record
- Decision: Rename `ApprovalPolicy` to `RunApprovalPolicy` (run-level CLI mode/callback) and introduce `WorkerApprovalPolicy` as the merged, effective policy for a worker (run policy + per-tool `.worker` config). Wrap toolsets at agent creation in `Worker.call` using the merged policy; remove recursive wrapping in `approval.py`.
- Decision: `WorkerApprovalPolicy` does not pre-merge toolset configs; it supplies run-level approval callback behavior while per-tool `_approval_config` is consulted by tool name at approval time.
- Decision: No recursive wrapping of nested workers; each worker wraps its own toolsets on call. Cycles are allowed and bounded by runtime depth.
- Decision: Pre-wrapped toolsets are not supported (update tests/helpers).
- Decision: Toolset-level "blocked" wins over `_approval_config.pre_approved`.
- Inputs:
  - Current recursive wrapping with unwrapping logic in `llm_do/runtime/approval.py`.
  - Mental model from `docs/notes/invocables-wrapping-mental-model.md`.
  - Desire to keep per-tool approval config scoped to workers (not shared toolsets) and to reuse the agent-creation hook.
  - Approval for delegation should be checked uniformly by tool name in the caller's policy, even when the tool is a worker.
  - `ToolsetRef` already carries per-worker `_approval_config` without mutating shared toolsets.
- Alternatives considered: Keep recursive wrapping at the run boundary; move approval into `WorkerRuntime.call`; pre-wrap in `build_entry`.
- Outcome: Adopt the `Worker.call` wrapping approach with explicit run-policy vs per-worker policy separation.
- Follow-ups:
  - Define how `RunApprovalPolicy` is surfaced to `Worker.call` without mutating shared instances.

## Tasks
- [x] Trace current wrapping flow and document where nested wrapping happens (update for new non-recursive plan).
- [x] Define how `RunApprovalPolicy` is exposed to `Worker.call` (context vs binding).
- [x] Rename `ApprovalPolicy` to `RunApprovalPolicy` and introduce `WorkerApprovalPolicy`.
- [x] Add `RunApprovalPolicy` to `WorkerRuntime.config` + `WorkerRuntimeProtocol` and expose via runtime `ctx`.
- [x] Implement `resolve_worker_policy(run_policy)` helper and `WorkerApprovalPolicy.wrap_toolsets(...)`.
- [x] Decide assembly hook in `Worker.call` (toolset wrapping + agent creation).
- [x] Decide pre-wrapped toolset handling (tests/live helper vs supported API).
- [x] Decide blocked vs pre_approved precedence (shell) and document expected semantics.
- [x] Plan migration steps for ToolsetRef and approval config handling (ensure per-worker `_approval_config` still works).
- [x] Implement run-level approval callback wiring (avoid mutating shared worker/toolset instances).
- [x] Implement toolset wrapping at agent creation in `Worker.call` (shallow wrap; each worker wraps itself).
- [x] Remove recursive wrapping in `approval.py` and update exports/usages accordingly.
- [x] Update tests: approval wrapping, nested worker approvals, ToolInvocable entry gating, cycles, repeat-run policy isolation.
- [x] Update docs (`docs/architecture.md`) to reflect new assembly flow.

## Current State
Run-level policy/worker policy wiring and shallow wrapping are in place; workers now build agents with approval-wrapped toolsets. Tests cover shallow wrapping, cycles, nested worker approvals, ToolInvocable entry gating, and per-run approval cache isolation. Docs reflect the new assembly flow.

## Risks / Edge Cases
- Run-level approval policy can leak across runs if stored on shared instances.
- Worker cycles are allowed; ensure wrapping avoids infinite recursion and rely on runtime depth checks.
- ToolInvocable entry calls should remain trusted; avoid gating entry invocation.
- `ToolsetRef`/`_approval_config` semantics must remain per-worker; avoid shared-state leakage.
- Approval UI currently omits worker identity; adding metadata is out of scope unless UI changes are planned.

## Notes
- Favor a pure, deterministic tool assembly path: runtime-provided approval callback + per-worker config + shallow toolset wrapping at agent creation.
- Approval gating stays in ApprovalToolset; `needs_approval()` on the called toolset can still refine/override decisions.
- Pre-wrapped toolsets appear only in tests/live helper; production wraps at run boundary today.
- Rationale: base toolsets stay unwrapped; each worker wraps at agent creation so tool schemas stay stable while worker-specific approval behavior is applied without recursive wrap/unwrap.
- Proposed wiring:
  - `RunApprovalPolicy` (renamed from `ApprovalPolicy`) lives on `WorkerRuntime.config` and is exposed via the runtime `ctx`.
  - `WorkerApprovalPolicy` is a small wrapper that holds the resolved approval callback + return_permission_errors and provides `wrap_toolsets(...)`.
  - `WorkerApprovalPolicy` does **not** pre-merge toolset configs; it passes per-tool `_approval_config` through to `ApprovalToolset`, which evaluates by tool name at call time.
  - `Worker.call` resolves a `WorkerApprovalPolicy` from `ctx.run_approval_policy` and wraps its own toolsets before spawning the child context (shallow wrapping, no recursion).
  - `run_entry` uses `RunApprovalPolicy` and only wraps toolsets for `ToolInvocable` entries to keep `ctx.deps.call` approval-gated; worker entries rely on `Worker.call`.
 - Tests run: `.venv/bin/python -m pytest tests/runtime/test_approval_wrapping.py tests/runtime/test_approval_wrappers.py`
