# Approval Unification

## Status
completed

## Prerequisites
- [x] Task 46: ApprovalToolset 0.9.0 API (completed)

## Goal
Remove redundant `requires_approval` mechanism from Invocables and use `ApprovalToolset` as the sole approval mechanism. User-initiated top-level calls don't need approval; LLM-initiated nested calls go through `ApprovalToolset`.

## Context
- Relevant files/symbols:
  - `llm_do/ctx_runtime/ctx.py`: `Context.approval`, `Context._execute()` (checks `entry.requires_approval`)
  - `llm_do/ctx_runtime/entries.py`: `WorkerEntry.requires_approval`, `ToolEntry.requires_approval`
  - `llm_do/ctx_runtime/cli.py:418-435`: entry-level approval setup (`headless_approval`, `--approve-all`/`--reject-all` for entries)
  - `pydantic_ai_blocking_approval`: `ApprovalToolset`, `ApprovalDecision`, `ApprovalRequest`
- Related tasks/notes/docs:
  - `docs/tasks/active/47-split-context-class.md` (depends on this task)
  - `docs/tasks/completed/46-approval-toolset-wrappers.md` (established 0.9.0 API)
- How to verify:
  - `uv run pytest`
  - Manual smoke: `llm-do --headless --approve-all` / `--reject-all` should work for nested invocations

## Decision Record
- Decision: Unify approval via `ApprovalToolset` only
- Inputs:
  - Two redundant mechanisms exist:
    1. `requires_approval` flag on Invocables + `Context.approval()` — static, per-invocable
    2. `ApprovalToolset` wrapping — dynamic, can inspect args/context
  - User-initiated top-level calls already have user consent (no approval needed)
  - LLM-initiated nested calls should go through `ApprovalToolset`
- Rationale:
  - One mechanism instead of two
  - `ApprovalToolset` is more flexible (can inspect args, context)
  - Simplifies `Context` / `WorkerRuntime` (no `approval` field needed)
- Behavior changes:
  - `--approve-all`/`--reject-all` will only affect `ApprovalToolset` (nested calls), not top-level entry
  - Top-level entry always proceeds (user typed the command)
  - Approvals are only requested for LLM-invoked actions; user-invoked top-level actions do not trigger approval
  - Headless mode: nested calls that require approval are denied by default; `--approve-all` allows them and `--reject-all` keeps deny

## Tasks
- [x] Remove `requires_approval` field from `WorkerEntry` and `ToolEntry`
- [x] Remove `requires_approval` from `CallableEntry` protocol (ctx.py)
- [x] Remove `Context.approval` field and `approval` parameter from `Context.__init__`
- [x] Remove entry-level approval check in `Context._execute()`
- [x] Remove entry-level approval setup in `cli.py` (lines ~418-435)
- [x] Update `--approve-all`/`--reject-all` to only affect `ApprovalToolset` (already the case via callback wrappers)
- [x] Update tests that use `requires_approval`
- [x] Update docs/CLI help to note approvals only apply to LLM-invoked actions and headless defaults
- [x] Run `uv run pytest`

## Current State
Implementation complete; approvals are unified under `ApprovalToolset` and tests are passing.

## Notes
- After this task, `ApprovalToolset` is the sole gatekeeper for approval
- Task 47 (Split Context) depends on this — will not need to migrate `approval` field
- This is a behavior change: entry-level gating is removed, only tool-level gating remains
- The distinction between "entry" and "tool" approval disappears — all invocations are just `ApprovalToolset` calls
