# Filesystem Toolset De-dup and Approval Simplification

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Deduplicate filesystem tool construction and simplify approval logic, prioritizing cleaner design over preserving existing behavior.

## Context
- Relevant files/symbols:
  - `llm_do/toolsets/filesystem.py` (FileSystemToolset.get_tools, FileSystemToolset.needs_approval)
- Related notes (inline summary):
  - Pattern 4: Add a small factory helper to build ToolsetTool objects to avoid repeated schema/validator boilerplate.
  - Pattern 5: Simplify approval logic to a small conditional; revisit the unknown-tool default.
- How to verify / reproduce:
  - `uv run pytest tests/runtime/test_approval_wrapping.py tests/test_toolset_args_validation.py tests/test_filesystem.py`

## Decision Record
- Decision: allow behavior changes when they improve clarity or simplicity.
- Inputs: current tool descriptions and approval settings are a reference point, not a constraint.
- Options: leave as-is vs helper method + compact approval logic with targeted behavior tweaks.
- Outcome: add a helper for tool creation and streamline approval; adjust semantics if it yields a cleaner, safer model.
- Follow-ups: none.

## Tasks
- [x] Add a `_make_tool(name, desc, args_cls)` helper to build ToolsetTool instances.
- [x] Refactor get_tools to use the helper; update descriptions if clarity improves.
- [x] Simplify needs_approval with a single branch for read/write; decide default for unknown tools.
- [x] Add a regression test that verifies `needs_approval_from_config` short-circuits for blocked/pre_approved in filesystem tools.
- [x] Double-check ReadOnlyFileSystemToolset behavior remains coherent (write_file blocked).

## Current State
Implementation complete: filesystem tool creation deduped, approval logic simplified with unknown tools requiring approval, and regression tests added. Checks pending.

## Notes
- Approval logic should remain coherent (list_files as read, write_file as write) unless a better model emerges.
