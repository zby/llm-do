# Worker Calls Feel Like Python Calls (A + C)

## Status
waiting for design decision

## Prerequisites
- [ ] design decision needed (runtime call normalization + runtime-bound callables)

## Goal
Make worker/tool calls feel like normal Python function calls while keeping an explicit runtime boundary for approvals and shared state.

## Context
- Relevant files/symbols: `llm_do/runtime/deps.py`, `llm_do/runtime/worker.py`, `llm_do/runtime/shared.py`, `docs/reference.md`, `docs/architecture.md`, `docs/concept.md`
- Related tasks/notes/docs: `docs/notes/worker-run-method-refactoring.md`, `docs/notes/runtime-scopes.md`
- How to verify / reproduce: add or update runtime-call tests; run `uv run pytest`; update examples or docs to demonstrate keyword-style calls and runtime-bound callables

## Motivation
- Current call pattern in tools is dict-heavy (`ctx.deps.call("name", {"input": ...})`), which breaks the Python function-call mental model.
- Top-level orchestration requires explicit runtime setup; we want a callable wrapper that feels like a function but still keeps runtime explicit and visible.
- The refactored runtime already splits config vs per-call state, so we can align call ergonomics without hiding approvals, tool resolution, or run-scoped state.

## Alternatives Considered
- Implicit runtime via contextvars: closest to Python semantics, but obscures approval/state flow and risks cross-task leakage under concurrency.
- Attribute-only proxy (`ctx.deps.tools.<name>(...)`): helps for tools but doesn’t help for top-level orchestration or binding a worker to a runtime.
- New orchestration helper class: could unify entry calls, but risks duplicating `Runtime` and increasing surface area.
- Keep status quo: lowest risk, but the mental-model mismatch remains and continues to show up in examples and docs.

## Decision Record
- Decision: Normalize worker/tool invocation inputs and add a runtime-bound callable wrapper to support function-like calls (A + C).
- Inputs:
  - Runtime is now explicit and split into shared config vs per-call state.
  - Tools already accept `RunContext[WorkerRuntime]` and can call into the runtime.
  - We want ergonomics improvements without making approvals and state implicit.
- Options:
  - A: Let the dispatcher accept keyword-style inputs and normalize into worker/tool schemas.
  - C: Provide a callable wrapper bound to a runtime and a specific worker/tool entry.
  - Combined A + C: keyword-style inputs + runtime-bound callables.
- Outcome (proposed):
  - Adopt A + C.
  - Keep runtime explicit; do not introduce implicit global runtime.
  - Prefer keyword-style usage in docs/examples; dict usage is allowed when passing through opaque tool inputs.
- Follow-ups:
  - Confirm exact normalization rules (string → `input`, BaseModel → dict, mapping passthrough).
  - Confirm where wrapper lives (runtime module vs worker module) and how it is surfaced.
  - Update docs/examples to standardize on function-like calls.

## Decisions To Make (with Proposed Resolutions)
- Should the dispatcher accept `**kwargs` and/or direct string input?
  - Proposed: accept `**kwargs` and direct string input mapped to `input` to match the WorkerInput schema.
- Should mapping inputs still be accepted?
  - Proposed: accept mappings for tool interoperability and internal call paths; document keyword style as the primary interface.
- Where does the runtime-bound callable wrapper live?
  - Proposed: runtime surface (so approval state and usage tracking remain explicit and discoverable).
- Should the wrapper be used inside tools (RunContext) as well as top-level orchestration?
  - Proposed: allow both, but do not make it the only path; keep direct dispatch for low-level control.
- Do we accept any backcompat breaks in examples/docs?
  - Proposed: update docs/examples to the new style even if it changes the public narrative; avoid extra compatibility scaffolding.

## Tasks
- [ ] Audit current call sites and tests to see where dict-only assumptions exist.
- [ ] Define input normalization rules that are consistent across tools and workers.
- [ ] Implement dispatcher normalization (A) and ensure `ToolsProxy` aligns.
- [ ] Implement runtime-bound callable wrapper (C) without hiding approvals or state.
- [ ] Update docs/examples to show the function-call mental model.
- [ ] Add tests covering keyword-style calls, direct string input, and runtime-bound callables.

## Current State
Task created; no implementation started.

## Notes
- Keep the runtime boundary explicit to preserve approval visibility and tooling behavior.
- Avoid naming or signature lock-in until the decision points above are confirmed.
