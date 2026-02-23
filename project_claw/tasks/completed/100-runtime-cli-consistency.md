# Runtime CLI Consistency

## Prerequisites
- [x] None.

## Goal
CLI help text, approval flag behavior, and internal helpers match actual runtime behavior across all modes.

## Tasks
- [x] Update `--model` help text to reflect override precedence.
- [x] Enforce mutual exclusivity for `--approve-all` and `--strict` in TUI mode.
- [x] Fix stale `--tui` error messaging.
- [x] Consolidate duplicate queue callbacks.
- [x] Remove or use the unused `create_toolset` context parameter.

## Current State
Completed: CLI help text updated, TUI approval flags validated, stale messaging fixed,
duplicate callback removed, and unused create_toolset param removed.

## Notes
- Origin: runtime/CLI review notes.
