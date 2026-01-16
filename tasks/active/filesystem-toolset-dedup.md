# Filesystem Toolset De-dup and Approval Simplification

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Deduplicate filesystem tool construction and simplify approval logic while preserving current behavior (including unknown tool = needs approval).

## Context
- Relevant files/symbols:
  - `llm_do/toolsets/filesystem.py` (FileSystemToolset.get_tools, FileSystemToolset.needs_approval)
- Related notes (inline summary):
  - Pattern 4: Add a small factory helper to build ToolsetTool objects to avoid repeated schema/validator boilerplate.
  - Pattern 5: Simplify approval logic to a small conditional, but keep unknown tool default to needs approval.
- How to verify / reproduce:
  - `uv run pytest tests/runtime/test_approval_wrapping.py tests/test_toolset_args_validation.py`

## Decision Record
- Decision: keep behavior identical, only reduce duplication.
- Inputs: current tool descriptions and approval settings must not change.
- Options: leave as-is vs helper method + compact approval logic.
- Outcome: add a helper for tool creation and streamline approval without changing semantics.
- Follow-ups: none.

## Tasks
- [ ] Add a `_make_tool(name, desc, args_cls)` helper to build ToolsetTool instances.
- [ ] Refactor get_tools to use the helper and keep descriptions identical.
- [ ] Simplify needs_approval with a single branch for read/write and keep unknown tool -> needs approval.
- [ ] Double-check ReadOnlyFileSystemToolset behavior (write_file blocked) remains unchanged.

## Current State
Not started.

## Notes
- Approval logic must preserve: list_files uses read approval, write_file uses write approval.
