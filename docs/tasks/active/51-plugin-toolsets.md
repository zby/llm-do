# Plugin Toolsets

## Status
ready for implementation

## Prerequisites
- [ ] none (independent of Context/Invocable refactoring)

## Goal
Move toolsets to `llm_do/toolsets/` directory and implement dynamic loading via class paths, enabling third-party toolsets without modifying llm-do core.

## Context
- Relevant files/symbols:
  - `llm_do/filesystem_toolset.py` → move to `llm_do/toolsets/filesystem.py`
  - `llm_do/shell/toolset.py` → move to `llm_do/toolsets/shell.py`
  - `llm_do/ctx_runtime/cli.py`: hardcoded toolset creation
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
- [ ] Create `llm_do/toolsets/` directory
- [ ] Move `filesystem_toolset.py` → `llm_do/toolsets/filesystem.py`
- [ ] Move `shell/toolset.py` → `llm_do/toolsets/shell.py`
- [ ] Create `llm_do/toolsets/__init__.py` with exports
- [ ] Create `llm_do/toolset_loader.py` with:
  - `_import_class(class_path)` — dynamic import
  - `create_toolset(class_path, config, context, approval_callback)` — factory
  - `build_toolsets(definition, context)` — build all toolsets for a worker
- [ ] Add alias mapping for built-ins (`shell`, `filesystem`, etc.)
- [ ] Update config format to support class paths as keys
- [ ] Replace hardcoded toolset creation in CLI with `build_toolsets()`
- [ ] Update imports across codebase
- [ ] Run `uv run pytest`

## Current State
Task activated from backlog. Design exists in archive doc. Ready to implement.

## Notes
- This is independent of Tasks 47-50 (Context/Invocable refactoring)
- Security: class loading is config-controlled (user's YAML), not LLM-controlled
- Third-party toolsets can implement `SupportsNeedsApproval` for smart approval or use `_approval_config` dict
