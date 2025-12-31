# Plugin Toolsets

## Status
completed

## Prerequisites
- [x] none (independent of Context/Invocable refactoring)

## Goal
Move toolsets to `llm_do/toolsets/` directory and implement dynamic loading via class paths, enabling third-party toolsets without modifying llm-do core.

## Context
- Relevant files/symbols:
  - `llm_do/toolsets/filesystem.py` (moved)
  - `llm_do/toolsets/shell.py` (moved)
  - `llm_do/toolset_loader.py`: class path loader and alias support
  - `llm_do/ctx_runtime/cli.py`: dynamic toolset creation via loader
  - `pydantic_ai_blocking_approval`: `ApprovalToolset`, `SupportsNeedsApproval`
- Related tasks/notes/docs:
  - `docs/notes/archive/toolset_plugin_architecture.md` (full design doc)
  - `docs/tasks/backlog/plugin-toolsets.md` (original backlog item)
- How to verify:
  - `uv run pytest`
  - Manual: workers using `shell` and `filesystem` toolsets still work

## Decision Record
- Decision: Dynamic loading with class paths and signature introspection
- Inputs:
  - Design doc in `docs/notes/archive/toolset_plugin_architecture.md`
  - Goal to enable third-party toolsets without core changes
- Options:
  - Hardcoded toolset wiring in CLI (status quo)
  - Plugin loader with class path config and dependency injection (chosen)
- Outcome:
  - Workers declare toolsets by full class path (e.g., `llm_do.toolsets.shell.ShellToolset`)
  - Loader introspects `__init__` signature to inject available deps (config, sandbox, etc.)
  - `ApprovalToolset` auto-detects `SupportsNeedsApproval` protocol
  - Support aliases for built-ins (`shell` → `llm_do.toolsets.shell.ShellToolset`)
- Follow-ups:
  - Update config examples/documentation when implementation lands

## Tasks
- [x] Create `llm_do/toolsets/` directory
- [x] Move `filesystem_toolset.py` → `llm_do/toolsets/filesystem.py`
- [x] Move `shell/toolset.py` → `llm_do/toolsets/shell.py`
- [x] Create `llm_do/toolsets/__init__.py` with exports
- [x] Create `llm_do/toolset_loader.py` with:
  - `_import_class(class_path)` — dynamic import
  - `create_toolset(class_path, config, context, approval_callback)` — factory
  - `build_toolsets(definition, context)` — build all toolsets for a worker
- [x] Add alias mapping for built-ins (`shell`, `filesystem`, etc.)
- [x] Update config format to support class paths as keys
- [x] Replace hardcoded toolset creation in CLI with `build_toolsets()`
- [x] Update imports across codebase
- [x] Run `uv run pytest`

## Current State
Completed.

- Toolsets moved under `llm_do/toolsets/` with exports for shell and filesystem.
- Added dynamic loader with alias support for built-ins and signature-based dependency injection.
- CLI uses `build_toolsets()` to resolve worker toolsets (built-ins, class paths, or Python-defined toolsets).
- Worker files now support class-path toolset keys alongside aliases.

## Notes
- This is independent of Tasks 47-50 (Context/Invocable refactoring)
- Security: class loading is config-controlled (user's YAML), not LLM-controlled
- Third-party toolsets can implement `SupportsNeedsApproval` for smart approval or use `_approval_config` dict
