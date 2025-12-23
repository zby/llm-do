# Textual CLI Port + Remove Legacy Runtime

## Prerequisites
- [ ] 60-context-runtime-llm-run (complete)
- [ ] Decision to switch interactive UI to the new runtime

## Goal
Port the Textual CLI to the new context-centric runtime, then remove the legacy runtime/CLI paths so there is only one current architecture.

## Tasks

### CLI Consolidation
- [ ] Consolidate `llm-run` into `llm-do` (deferred from task 60)
  - Single entry point with mode detection or subcommands
  - Preserve all flags from both CLIs

### Textual UI Port
- [ ] Port Textual CLI to use `llm_do/runtime` execution flow
- [ ] Verify approvals/tool loading behave identically in the UI
- [ ] Wire interactive approval prompts (replaces headless PermissionError)

### Cleanup
- [ ] Remove legacy runtime modules and related CLI paths
- [ ] Update docs and examples to reference the new runtime only
- [ ] Move validated `examples-new/` to `examples/` (replace old examples)

### Tests (Deferred from Task 60)
- [ ] Port `test_cli_async.py` (488 lines) - CLI integration tests
- [ ] Port `test_display_backends.py` (351 lines) - UI backend tests
- [ ] Run `uv run pytest` and fix any breakage

## Current State
Not started. Waiting on `llm_do/runtime` + `llm-run` headless CLI.

## Notes
- Keep this phase focused: once Textual CLI is ported, delete old runtime code.
- The headless `llm-run` from task 60 raises `PermissionError` for unapproved tools; this task adds interactive prompts.
