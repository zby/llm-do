# Simplify Invocable Wrapping

## Status
waiting for design decisions

## Prerequisites
- [x] decide how ApprovalPolicy is stored for a run (store on Worker vs runtime context)
- [x] decide assembly hook (wrap toolsets at agent creation in Worker.call)
- [ ] decide pre-wrapped toolset handling (tests/live helper vs supported API)
- [ ] decide whether pre_approved can bypass blocked decisions (shell)

## Goal
Move approval wrapping to agent creation by storing the active ApprovalPolicy on Worker instances (per-run binding) so that:
- each worker wraps its own toolsets when building its Agent (no recursive wrap/unwrap)
- nested worker calls inherit the same run policy and are still approval-gated
- ToolInvocable entry calls remain un-gated by approvals (current behavior)
- per-worker `_approval_config` behavior is preserved
- tests and docs reflect the new assembly flow

## Context
- Relevant files/symbols:
  - `llm_do/runtime/approval.py` (`_wrap_toolsets_with_approval`, `wrap_entry_for_approval`)
  - `llm_do/runtime/worker.py` (`Worker.toolsets`, `ToolInvocable`)
  - `llm_do/toolsets/loader.py` (`ToolsetRef`, toolset resolution)
  - `llm_do/cli/main.py` (toolset assembly for workers and entries)
  - `llm_do/runtime/runner.py` (run boundary and approval policy)
  - `llm_do/runtime/context.py` (execution and tool dispatch)
- Related tasks/notes/docs:
  - `docs/notes/invocables-wrapping-mental-model.md`
  - `docs/notes/per-worker-approval-config.md`
  - `docs/architecture.md` (approval/toolset flow)
- How to verify / reproduce:
  - `uv run pytest tests/runtime/test_approval_wrappers.py`
  - Update/add tests: `tests/runtime/test_approval_wrapping.py` (no recursive wrap/unwrap, cycles),
    a nested-worker approval test, a ToolInvocable entry test (entry calls remain un-gated),
    and a repeat-run test to confirm ApprovalPolicy does not leak across runs.
  - Update `tests/live/conftest.py` helper if pre-wrapped toolsets are removed.

## Decision Record
- Decision: Attach ApprovalPolicy to Worker instances at the run boundary and wrap toolsets at agent creation in `Worker.call` (shallow wrap + bind nested workers). Remove recursive wrapping in `approval.py`. ApprovalPolicy remains a run-level policy; per-worker approval config refers to `_approval_config` only.
- Inputs:
  - Current recursive wrapping with unwrapping logic in `llm_do/runtime/approval.py`.
  - Mental model from `docs/notes/invocables-wrapping-mental-model.md`.
  - Desire to attach approval policies to workers, not shared toolsets, and to reuse the agent-creation hook.
  - Approval for delegation should be checked uniformly by tool name in the caller's policy, even when the tool is a worker.
  - `ToolsetRef` already carries per-worker `_approval_config` without mutating shared toolsets.
- Options:
  - A) Store ApprovalPolicy on Worker + wrap at `Worker.call` (chosen).
  - B) Keep recursive wrapping at the run boundary (status quo).
  - C) Move approval into `WorkerRuntime.call` (no ApprovalToolset wrapper).
  - D) Pre-wrap in `build_entry` (policy locked to build time).
- Outcome: Adopt A with uniform approval gating for delegation.
- Follow-ups:
  - Define how to bind ApprovalPolicy to Worker without mutating shared instances.
  - Decide how to bind nested workers when wrapping toolsets (shallow binding vs caching).
  - Decide how to treat pre-wrapped toolsets (likely drop and update tests/helpers).
  - Decide if blocked decisions always override pre_approved (shell currently returns early on pre_approved).

## Tasks
- [ ] Trace current wrapping flow and document where nested wrapping happens.
- [ ] Define how ApprovalPolicy is stored on Worker (field name, default, lifecycle).
- [ ] Decide assembly hook in `Worker.call` (toolset wrapping + agent creation).
- [ ] Decide pre-wrapped toolset handling (tests/live helper vs supported API).
- [ ] Decide blocked vs pre_approved precedence (shell) and document expected semantics.
- [ ] Plan migration steps for ToolsetRef and approval config handling (ensure per-worker `_approval_config` still works).
- [ ] Implement policy binding at run boundary (e.g., replace entry/nested workers with bound copies).
- [ ] Implement toolset wrapping at agent creation in `Worker.call` (shallow wrap + bind nested workers).
- [ ] Remove recursive wrapping in `approval.py` and update exports/usages accordingly.
- [ ] Update tests: approval wrapping, nested worker approvals, ToolInvocable entry gating, cycles, repeat-run policy isolation.
- [ ] Update docs (`docs/architecture.md`) to reflect new assembly flow.

## Current State
Decisions captured for storing ApprovalPolicy on Worker and wrapping toolsets at agent creation. Open design items: policy binding lifecycle, nested worker binding strategy, pre-wrapped toolset handling, and blocked-vs-pre_approved precedence.

## Risks / Edge Cases
- ApprovalPolicy stored on Worker can leak across runs if shared instances are mutated.
- Worker cycles were handled by recursive wrapping; new binding approach must remain cycle-safe.
- ToolInvocable entry calls should remain trusted; avoid gating entry invocation.
- `ToolsetRef`/`_approval_config` semantics must remain per-worker; avoid shared-state leakage.
- Approval UI currently omits worker identity; adding metadata is out of scope unless UI changes are planned.

## Notes
- Favor a pure, deterministic tool assembly path: policy-bound Worker + shallow toolset wrapping at agent creation.
- Approval gating stays in ApprovalToolset; `needs_approval()` on the called toolset can still refine/override decisions.
- Pre-wrapped toolsets appear only in tests/live helper; production wraps at run boundary today.
