# Shared Tool Plane Builder (Worker + Entry)

## Status
in progress

## Prerequisites
- [ ] none

## Goal
Unify tool plane setup so `Runtime.run_entry()` and `Worker._call_internal()` share the same builder for toolset instantiation, approval wrapping, invocation metadata, and cleanup. Behavior must remain identical to current entry/worker parity.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/worker.py` (`Worker._call_internal`, attachment handling)
  - `llm_do/runtime/shared.py` (`Runtime.run_entry`, `_build_entry_frame`)
  - `llm_do/runtime/deps.py` (`WorkerRuntime.spawn_child`, `WorkerRuntime.call`)
  - `llm_do/runtime/call.py` (`CallFrame`, `CallConfig`)
  - `llm_do/runtime/approval.py` (`wrap_toolsets_for_approval`)
  - `llm_do/toolsets/loader.py` (`instantiate_toolsets`)
  - `llm_do/toolsets/attachments.py` (`AttachmentToolset`)
  - `examples/pitchdeck_eval_direct/` (script-mode example to align with step 3/4)
- Related tasks/notes/docs:
  - `docs/notes/unified-entry-function-design.md`
- How to verify / reproduce:
  - Run runtime tests covering approvals and tool events (entry + worker paths).
  - Ensure attachments still resolve via runtime project root.
  - Confirm entry toolsets are wrapped exactly once, same as worker toolsets.
  - Verify entry tool events still attribute to the entry name via `invocation_name`.

## Known Behavior To Preserve
- Entry toolsets are approval-wrapped per run policy (`return_permission_errors` honored).
- `CallFrame.invocation_name` is set for entry and worker calls; tool events use it.
- Depth is CallFrame stack depth (entry=0, worker child=1); tool calls do not change depth.
- Attachment resolution uses runtime project root (`RuntimeConfig.project_root`) and stays in worker path.

## Decision Record
- Decision: Keep it simple; extract a shared helper (prefer `runtime/shared.py`) that owns toolset instantiation, approval wrapping, and cleanup. Use an async context manager or small helper object so callers can guarantee cleanup in `finally`.
- Inputs: `docs/notes/unified-entry-function-design.md` (post-v1 cleanup).
- Options:
  - Helper in `runtime/shared.py` (preferred; already owns `cleanup_toolsets`).
  - New `runtime/tool_plane.py` only if import cycles force it.
- Outcome: Use `runtime/shared.py` unless a cycle appears.
- Follow-ups: None; registry-free script mode is out of scope.

## Tasks
- [x] Create a shared builder (async context manager or helper) that instantiates toolsets, wraps approvals, and guarantees cleanup.
- [x] Use the shared builder in `Runtime.run_entry` for entry toolsets (keep `CallFrame.invocation_name` intact).
- [x] Use the shared builder in `Worker._call_internal` for worker toolsets (retain attachment handling in worker path).
- [x] Confirm no behavioral drift: approvals, event attribution, depth, and project-root attachment resolution.
- [x] Check `examples/pitchdeck_eval_direct/` matches step 3 (script mode) expectations after refactor.
- [x] Add a step 4 refactor example to `examples/pitchdeck_eval_direct/` that bypasses the tool plane (raw Python), with clear commentary on observability tradeoffs.
- [x] Update docs/comments only if behavior changes (should not be needed).

## Current State
Shared builder wired into entry + worker paths. Step 4 raw Python example added to
`examples/pitchdeck_eval_direct/`. Checks run; behavior aligned.

## Notes
- Keep depth semantics unchanged (CallFrame stack depth: entry=0, worker=1).
- Do not introduce a ToolRouter in this task.
- Keep approvals runtime-wide (no per-call bypass).
