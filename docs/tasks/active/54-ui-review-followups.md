# UI Review Followups

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Address the UI review findings by aligning streaming output and TUI rendering with headless output, and remove or replace dead UI code.

## Context
- Relevant files/symbols: `llm_do/ui/events.py` (TextResponseEvent), `llm_do/ui/display.py` (HeadlessDisplayBackend, RichDisplayBackend), `llm_do/ui/widgets/messages.py` (ToolCallMessage, AssistantMessage, ApprovalMessage), `llm_do/ui/app.py` (LlmDoApp.CSS, approval flow)
- Related tasks/notes/docs: `docs/notes/reviews/review-ui.md`, `docs/notes/tool-output-rendering-semantics.md`
- How to verify / reproduce: run `llm-do` in TUI (`--tui`, `--chat`) and headless (`-vv`, `--json`) to compare streaming output and approval/tool rendering

## Decision Record
- Decision: TUI renders assistant/tool output as literal text; tool call args use safe JSON with truncation indicator; dead CSS removed; approvals stay in the pinned panel (no scrollback logging); streaming uses deltas plus a final complete response event.
- Inputs: `docs/notes/reviews/review-ui.md`, user decisions on truncation indicator and literal text.
- Options: allow markup vs literal; scrollback approvals vs panel-only; truncation behavior vs full payloads; delta-only streaming vs final response event.
- Outcome: use literal text with explicit truncation indicator "… [truncated]."; keep approvals in the pinned panel; stream deltas inline and emit a final `TextResponseEvent`.
- Follow-ups: decide whether to remove or repurpose `ApprovalMessage` for panel-only approvals.

## Tasks
- [x] Decide streaming verbosity behavior and whether to emit a final `TextResponseEvent`.
- [x] Make TUI tool-call formatting robust (safe JSON, truncation consistent with headless).
- [x] Decide and implement markup handling for assistant/tool output (literal vs markup).
- [x] Remove unused CSS (dead class blocks in `LlmDoApp.CSS`).
- [ ] Remove or repurpose `ApprovalMessage` if approvals remain panel-only.
- [ ] Update docs/tests as needed.

## Current State
Streaming parity decisions recorded; tool formatting, literal rendering, and CSS cleanup implemented. `ApprovalMessage` cleanup remains open.

## Notes
- Findings recorded in `docs/notes/reviews/review-ui.md`.
