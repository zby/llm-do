# Per-Worker Toolset Instantiation

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Default toolset instances to per-worker-call scope, with an explicit scope option (call/run/global) so stateful tools like browsers do not leak across workers unless opted in.

## Context
- Relevant files/symbols:
  - llm_do/runtime/registry.py (build_invocable_registry, toolset catalog)
  - llm_do/toolsets/loader.py (build_toolsets resolution)
  - llm_do/runtime/worker.py (Worker.call toolset wiring)
  - llm_do/runtime/deps.py (WorkerRuntime.spawn_child, tool lookup)
  - llm_do/toolsets/builtins.py (builtin toolset construction)
  - llm_do/toolsets/approval.py (per-tool approval config on toolset instances)
- Related tasks/notes/docs:
  - docs/architecture.md (runtime scopes)
  - docs/notes/reviews/review-ctx-runtime.md (per-worker approval config mutates shared toolset instances)
- How to verify / reproduce:
  - Create a stateful toolset (e.g., browser or counter) and use it in two workers; confirm state does not leak between workers by default.

## Decision Record
- Decision: Toolsets are instantiated per worker call by default; introduce a factory/spec with a scope option to allow run/global reuse when explicitly configured.
- Inputs: Stateful tools (browser) need isolation; current shared instances cause approval config mutation and state leaks.
- Options: Keep global instances; per-call instances only; per-call with optional run/global scope; move state into CallFrame instead of instances.
- Outcome: Choose per-call instantiation with explicit scope override; keep stateful toolsets safe by default.
- Follow-ups: Update architecture/reference docs to describe scope and instantiation model.

## Tasks
- [ ] Define a toolset spec/factory interface and scope enum (call/run/global) used by the registry.
- [ ] Update registry/toolset resolution to store specs, not shared instances; builtins become factories.
- [ ] Instantiate toolsets per worker call, with scoped caching for run/global as configured.
- [ ] Remove or refactor per-tool approval config mutation on shared instances; apply config to per-call instances.
- [ ] Add tests for state isolation (per-call) and scoped reuse (run/global).
- [ ] Update docs: architecture, reference, and any example notes.

## Current State
Task created; design and implementation not started.

## Notes
- Watch for toolset instances used as workers (Worker extends AbstractToolset); ensure worker toolsets remain per-call while worker identity stays stable.
- Consider how code entry points that expose tool tools by name (ToolInvocable) should acquire scoped instances.
