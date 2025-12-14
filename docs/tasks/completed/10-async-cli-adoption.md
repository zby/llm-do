# Async CLI Adoption

## Prerequisites
- [x] Async CLI prototype exists in `experiments/async_cli/`
- [x] Native async approval callback implemented (no longer uses bridge pattern)
- [x] pydantic-ai-blocking-approval supports async callbacks

## Goal
Promote async CLI from experiment to production, replacing the sync CLI as the default.

## Tasks

### Phase 1: Code Migration
- [x] Create `llm_do/cli_async.py` from `experiments/async_cli/main.py`
- [x] Move `experiments/async_cli/display.py` to `llm_do/ui/display.py`
- [x] Update imports to use package paths instead of experiment paths

### Phase 2: Entry Point Update
- [x] Update `pyproject.toml` entry point to use async CLI
- [x] Ensure `llm-do` command uses `asyncio.run(run_async_cli())`
- [x] Keep sync `run_worker()` available for programmatic use

### Phase 3: Test Coverage
- [x] Add tests for async CLI argument parsing
- [x] Add tests for approval callback integration
- [x] Add tests for message callback event flow
- [x] Test `--json` mode output format

### Phase 4: Cleanup
- [x] Remove `experiments/async_cli/` after migration complete
- [x] Update `docs/notes/async_cli_event_loop.md` to reflect production status (N/A - file never existed, architecture is self-documenting)
- [x] Update CLAUDE.md if any guidance changes (no changes needed)

## Current State
- **COMPLETED**: Async CLI is now the default entry point
- `llm_do/cli_async.py` is the new async CLI implementation
- `llm_do/ui/display.py` contains display backend abstractions
- Sync CLI (`llm_do/cli.py`) retained for `init_project` and programmatic use
- 14 new tests in `tests/test_cli_async.py`

## Key Files
- Production: `llm_do/cli_async.py`, `llm_do/ui/display.py`
- Entry point: `pyproject.toml` → `llm_do.cli_async:main`
- Legacy sync: `llm_do/cli.py` (kept for init and programmatic use)
