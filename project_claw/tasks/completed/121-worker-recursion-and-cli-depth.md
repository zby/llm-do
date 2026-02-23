# Worker Recursion and CLI Max Depth

## Status
completed

## Prerequisites
- [x] design decision needed: self-recursion exposure (default vs explicit toolset)
- [x] design decision needed: approval policy for worker-as-tool (capability-based vs legacy gating)

## Goal
Enable intentional recursive workers (including self recursion) and expose configurable max depth via CLI.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/registry.py` (worker toolset resolution; self filter)
  - `llm_do/runtime/worker.py` (Worker tool behavior; approval policy hook point)
  - `llm_do/runtime/approval.py` (ApprovalToolset wrapping)
  - `llm_do/runtime/shared.py` (RuntimeConfig.max_depth)
  - `llm_do/cli/main.py` (CLI options and Runtime wiring)
  - `llm_do/toolsets/approval.py` (set_toolset_approval_config)
- Related tasks/notes/docs:
  - `docs/notes/recursive-problem-patterns.md`
  - `docs/notes/messages-as-locals.md`
- How to verify / reproduce:
  - Add a recursive worker example (self toolset) and confirm it runs within max depth.
  - CLI accepts `--max-depth` (or similar) and enforces depth via RuntimeConfig.
  - Tests for self-recursion and depth enforcement pass.

## Decision Record
- Decision: Keep toolsets list authoritative; enable recursion only when worker explicitly lists itself in toolsets. Use capability-based approvals (side-effects only) with legacy gating available via subclassing or per-toolset approval config. No special `self` alias.
- Inputs: Recursive patterns note, current approval gating tests, toolset capability model.
- Options:
  - Allow self only when explicitly listed in `toolsets` (status quo + remove self filter).
  - Auto-include self tool in every worker (implicit recursion capability).
  - Add reserved alias (e.g., `self`) for explicit recursion without name collision.
  - Provide a generic "entry call" toolset to invoke any invocable by name.
  - Capability-based approvals: pre-approve worker-as-tool by default; override via subclass or `set_toolset_approval_config`.
  - Legacy gating option: keep "all LLM tool calls require approval" as opt-in.
- Outcome: Select explicit self toolset listing + capability-based approvals; leave legacy gating as opt-in.
- Follow-ups: update tests that currently assume nested worker calls are approval gated; plan for bulk approvals with scoped approval callbacks and defer full DeferredTools support.

## Tasks
- [x] Enable self-recursive toolset resolution (remove or adjust self filter).
- [x] Add CLI `--max-depth` (or equivalent) wired to RuntimeConfig.
- [x] Implement capability-based approval defaults for Worker tool calls.
- [x] Add worker-level bulk approval option by scoping approval callback in `Worker.call()` (single approval gates child toolsets).
- [x] Add/update tests for self recursion and depth enforcement.
- [x] Update docs/examples to show recursive worker pattern.

## Current State
Self recursion is enabled via explicit toolset listing, worker calls default to pre-approved, bulk approvals can be scoped per worker call, and CLI exposes max depth. Tests and docs updated.

## Notes
- Naming collisions are acceptable for now; revisit if auto-including self or aliasing.
- Bulk approvals can later migrate to DeferredTools for better UX; keep implementation minimal for now.
