# Docstring Pruning for Cleaner Code

## Status
complete

## Prerequisites
- [ ] none

## Goal
Remove or tighten docstrings that restate obvious behavior or type hints, while preserving docstrings that carry real contracts or non-obvious behavior.

## Context
- Relevant files/symbols (initial candidates, verify before editing):
  - `llm_do/toolsets/shell/execution.py`
  - `llm_do/toolsets/shell/toolset.py`
  - `llm_do/toolsets/filesystem.py`
  - `llm_do/runtime/worker.py`
  - `llm_do/ui/events.py`
  - `llm_do/runtime/discovery.py`
  - `llm_do/cli/main.py` (keep module docstring; used as CLI help via `__doc__`)
- Related notes (inline summary):
  - Pattern 6: remove docstrings when they only restate type hints or function names; keep for non-obvious behavior, side effects, or public contracts.
- How to verify / reproduce:
  - Run targeted tests for touched modules; if unsure, `uv run pytest`.

## Decision Record
- Decision: prioritize clarity over raw SLOC; reduce noise in docstrings that do not add information.
- Inputs: current docstrings are verbose and often restate signature/body.
- Options: keep all docstrings vs prune only redundant ones vs aggressive removal.
- Outcome: remove/rewrite only redundant docstrings; preserve docs that capture contracts, security, or usage.
- Follow-ups: none.

## Tasks
- [x] Inventory docstrings in candidate files; tag each as keep/shorten/remove.
- [x] Remove docstrings that only restate name/args/returns or repeat obvious code.
- [x] Keep docstrings that document non-obvious behavior, side effects, security constraints, or API contracts.
- [x] Avoid removing module docstrings used for CLI help or documentation.
- [x] Update tests if any rely on docstrings (unlikely; confirm).

## Current State
Complete. Removed 10 truly redundant docstrings:
- `ShellArgs`, `ReadResult`, `ReadFileArgs`, `WriteFileArgs`, `ListFilesArgs` class docstrings
- `id` and `config` property docstrings in `ShellToolset` and `FileSystemToolset`
- `ReadOnlyFileSystemToolset` class docstring

All 302 tests pass.

## Notes
- Prefer shortening to a single sentence when a docstring adds value but is verbose.
- Preserve security boundary notes (e.g., shell and filesystem toolsets).
