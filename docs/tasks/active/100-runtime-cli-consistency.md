# Runtime CLI Consistency

## Prerequisites
- [ ] None.

## Goal
CLI help text, approval flag behavior, and internal helpers match actual runtime behavior across all modes.

## Tasks
- [ ] Update `--model` help text to reflect override precedence.
- [ ] Enforce mutual exclusivity for `--approve-all` and `--strict` in TUI mode.
- [ ] Fix stale `--tui` error messaging.
- [ ] Consolidate duplicate queue callbacks.
- [ ] Remove or use the unused `create_toolset` context parameter.

## Current State
Created from review notes; not started.

## Notes
- Origin: runtime/CLI review notes.
