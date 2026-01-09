# Toolset Approval Config on Registry Instances

## Status
ready for completion

## Prerequisites
- [ ] none

## Goal
Move approval policy to toolset instances (registry-level) and remove per-worker toolset config in `.worker` files.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/registry.py`
  - `llm_do/toolsets/loader.py`
  - `llm_do/runtime/approval.py`
  - `llm_do/runtime/worker.py`
  - `llm_do/toolsets/filesystem.py`
  - `llm_do/runtime/discovery.py`
  - `docs/reference.md`
  - `docs/notes/toolset_definitions_and_approvals.md`
  - examples under `examples/`
  - tests under `tests/`
- Related tasks/notes/docs:
  - `docs/notes/toolset_definitions_and_approvals.md`
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Use attribute-based approval config on toolset instances.
- Inputs: discussion 2025-01-08 (this thread).
- Options: attribute-based vs side-map vs registration record.
- Outcome:
  - Attribute name: `__llm_do_approval_config__`.
  - Built-ins registered as module-level instances where possible; filesystem toolsets are constructed per worker to set `base_path`.
  - `.worker` toolset configs are names only (no per-worker config).
  - Filesystem toolsets are `filesystem_rw` and `filesystem_ro` (separate read-only class).
  - `base_path` is derived from the worker CWD.
- Follow-ups:
  - Optionally add `@llm_do_tool` helper decorator to set per-tool approval config on FunctionToolset.

## Tasks
- [x] Add built-in toolset entries for `filesystem_rw`/`filesystem_ro` and shell profiles with approval config attributes.
- [x] Change registry build to use built-in instances + discovered Python toolsets (instances only).
- [x] Remove per-worker `_approval_config` extraction and `Worker.toolset_approval_configs`.
- [x] Update approval wrapping to read `__llm_do_approval_config__` from toolset instances.
- [x] Enforce `.worker` toolset references as names only (reject config mappings).
- [x] Add a read-only filesystem toolset class; set `base_path` from CWD; expose only read/list for RO.
- [x] Update docs/examples to the new toolset config model.
- [x] Update tests for toolset loading/approvals changes.
- [x] Update docs/examples/tests to match the new toolset model (CWD base path, `filesystem_rw`/`filesystem_ro`).

## Current State
Implementation complete: built-in toolset registry + read-only filesystem toolset, approval config attribute support, name-only toolset references in worker YAML, examples/docs/tests updated. Pending task wrap-up and archive note.

## Notes
- If toolsets do not implement `needs_approval`, `ApprovalToolset` must receive per-tool config dict.
- Per-tool config should live on toolset instance attribute or derived at wrap time.
- Built-ins should be always available without requiring a Python toolset file.
