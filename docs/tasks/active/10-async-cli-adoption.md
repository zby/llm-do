# Async CLI Adoption

## Prerequisites
- [x] Async CLI prototype exists in `experiments/async_cli/`
- [x] Native async approval callback implemented (no longer uses bridge pattern)
- [x] pydantic-ai-blocking-approval supports async callbacks

## Goal
Promote async CLI from experiment to production, replacing the sync CLI as the default.

## Tasks

### Phase 1: Code Migration
- [ ] Create `llm_do/cli_async.py` from `experiments/async_cli/main.py`
- [ ] Move `experiments/async_cli/display.py` to `llm_do/ui/display.py`
- [ ] Update imports to use package paths instead of experiment paths
- [ ] Add `--sync` flag to fall back to old CLI behavior (deprecation path)

### Phase 2: Entry Point Update
- [ ] Update `pyproject.toml` entry point to use async CLI
- [ ] Ensure `llm-do` command uses `asyncio.run(run_async_cli())`
- [ ] Keep sync `run_worker()` available for programmatic use

### Phase 3: Test Coverage
- [ ] Add tests for async CLI argument parsing
- [ ] Add tests for approval callback integration
- [ ] Add tests for message callback event flow
- [ ] Test `--json` mode output format

### Phase 4: Cleanup
- [ ] Remove `experiments/async_cli/` after migration complete
- [ ] Update `docs/notes/async_cli_event_loop.md` to reflect production status
- [ ] Update CLAUDE.md if any guidance changes

## Current State
- Experiment is working with native async callbacks
- Worker runs directly in main event loop (no background thread)
- Message callback uses direct queue (no threadsafe wrapper needed)
- Tested manually with greeter worker

## Notes
- The async CLI now uses `_make_async_approval_callback()` which returns a native async callback
- `run_in_executor` is used for blocking `console.input()` calls
- DisplayBackend abstraction already supports Rich and JSON backends
- Consider whether to keep experiment around during transition or migrate directly

## Key Files
- Source: `experiments/async_cli/main.py`, `experiments/async_cli/display.py`
- Target: `llm_do/cli_async.py`, `llm_do/ui/display.py`
- Related: `llm_do/cli.py` (current sync CLI)
