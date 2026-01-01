# UI Review Followups

## Status
waiting for design decision

## Prerequisites
- [ ] design decision needed (streaming output behavior, markup handling, approval logging)

## Goal
Address the UI review findings by aligning streaming output and TUI rendering with headless output, and remove or replace dead UI code.

## Context
- Relevant files/symbols: `llm_do/ui/events.py` (TextResponseEvent), `llm_do/ui/display.py` (HeadlessDisplayBackend, RichDisplayBackend), `llm_do/ui/widgets/messages.py` (ToolCallMessage, AssistantMessage, ApprovalMessage), `llm_do/ui/app.py` (LlmDoApp.CSS, approval flow)
- Related tasks/notes/docs: `docs/notes/reviews/review-ui.md`
- How to verify / reproduce: run `llm-do` in TUI (`--tui`, `--chat`) and headless (`-vv`, `--json`) to compare streaming output and approval/tool rendering

## Decision Record
- Decision:
- Inputs:
- Options:
- Outcome:
- Follow-ups:

## Tasks
- [ ] Decide streaming verbosity behavior and whether to emit a final `TextResponseEvent`.
- [ ] Make TUI tool-call formatting robust (safe JSON, truncation consistent with headless).
- [ ] Decide and implement markup handling for assistant/tool output (literal vs markup).
- [ ] Remove unused CSS or wire classes; decide whether approvals should show in scrollback.
- [ ] Update docs/tests as needed.

## Current State
Task created from UI review; no implementation started.

## Notes
- Findings recorded in `docs/notes/reviews/review-ui.md`.
