# UI Event Handling Cleanup

## Prerequisites
- [x] ui-system-reimplementation.md completed

## Goal
Clarify and enforce ASCII guarantees for plain-text outputs after the UI system reimplementation.

## Tasks
- [ ] Decide whether "ASCII-only" applies only to system strings or also to user/model content.
- [ ] If user/model content must be ASCII-only, add sanitization in `render_text()` paths.
- [ ] Add or adjust tests to cover ASCII-only output expectations (including user/model content if required).

## Current State
Core UI refactor done. System strings are ASCII, but user/model content is not sanitized.

## Notes
- Spec archived in `docs/notes/archive/ui-specification.md`.
- This is a follow-up cleanup task; implementation depends on the ASCII policy decision.
