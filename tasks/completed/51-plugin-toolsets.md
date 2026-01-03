# Plugin Toolsets

## Status
completed

## Prerequisites
- [x] none (independent of Context/Invocable refactoring)

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
  - `tasks/backlog/plugin-toolsets.md` (original backlog item)
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
  - `create_toolset(toolset_ref, config, context)` — factory
  - `build_toolsets(definition, context)` — build all toolsets for a worker
- [x] Add alias mapping for built-ins (`shell`, `filesystem`, etc.)
- [x] Update config format to support class paths as keys
- [x] Replace hardcoded toolset creation in CLI with `build_toolsets()`
- [x] Update imports across codebase
- [x] Run `uv run pytest`

## Current State
Completed: toolsets moved under `llm_do/toolsets/`, dynamic class-path loader added,
CLI now builds toolsets via `build_toolsets()`, and the full test suite passes.

## Lessons Learned from Branch Review

Branch `origin/codex/implement-plugin-toolsets-documentation` attempted this task but has issues:

### 1. Naming Conflict
The branch renamed `WorkerRuntime` → `Context`, but main just did the opposite rename. **Cannot merge as-is.**

### 2. Redundant ApprovalToolset Wrapping
The branch wraps toolsets with `ApprovalToolset` in **three places**, each with `isinstance()` guards:

```python
# 1. In create_toolset() - wraps if approval_callback provided
if approval_callback:
    toolset = ApprovalToolset(inner=toolset, ...)

# 2. In build_toolsets() - wraps again if not already wrapped
if context.approval_callback and not isinstance(toolset, ApprovalToolset):
    toolset = ApprovalToolset(...)

# 3. In _wrap_toolsets_with_approval() - called later from run()
if isinstance(toolset, ApprovalToolset):
    continue  # skip
```

This avoids double-wrapping via `isinstance()` checks but the logic is duplicated and confusing.

### Cleaner Approach

**Wrap in ONE place only:**

1. **`create_toolset()`** — just creates the raw toolset (no wrapping)
2. **`build_toolsets()`** — handles ALL wrapping in one place:
   ```python
   def build_toolsets(definition, context) -> list[AbstractToolset]:
       toolsets = []
       for class_path, config in definition.items():
           toolset = create_toolset(class_path, config, context)
           if context.approval_callback:
               toolset = ApprovalToolset(
                   inner=toolset,
                   approval_callback=context.approval_callback,
                   config=config.get("_approval_config"),
               )
           toolsets.append(toolset)
       return toolsets
   ```
3. **`_wrap_toolsets_with_approval()`** — add `isinstance(ApprovalToolset)` guard to skip already-wrapped toolsets (for toolsets from other sources like `available_toolsets`)

### What to Salvage from the Branch
- `ToolsetBuildContext` dataclass — clean way to pass context/deps
- `_import_class()` helper — simple dynamic import
- `isinstance(ApprovalToolset)` guard in `_wrap_toolsets_with_approval()` — prevents double-wrapping
- Toolset reorganization to `llm_do/toolsets/` directory

## Notes
- This is independent of Tasks 47-50 (Context/Invocable refactoring)
- Security: class loading is config-controlled (user's YAML), not LLM-controlled
- Third-party toolsets can implement `SupportsNeedsApproval` for smart approval or use `_approval_config` dict
