# UI System Review

## Context
Review of the UI system for bugs, inconsistencies, and overengineering.

## Findings
- Streaming verbosity >= 2 is fragmented and loses completion context. `HeadlessDisplayBackend` appends a newline per event while `TextResponseEvent.render_text` returns raw deltas, so each delta becomes its own line. `RichDisplayBackend` uses `console.print` without `end=""`, so deltas also land on separate lines. `_run_streaming` emits only delta events (no final `TextResponseEvent`), and CLI output skips printing the final result at verbosity >= 2. Net effect: streaming output is noisy and lacks a final response marker. (`llm_do/ui/display.py`, `llm_do/ui/events.py`, `llm_do/runtime/invocables.py`)
- Tool call rendering in the TUI can throw `TypeError` for non-JSON-serializable args and has no truncation for large payloads. `_format_tool_call` calls `json.dumps` without `default=str`, and it bypasses the `MAX_ARGS_DISPLAY` limit used in headless/rich backends. The app catches the exception and shows a generic "Display error", but the tool call entry is lost. (`llm_do/ui/widgets/messages.py`)
- Model output is rendered as Rich markup inside `Static` widgets. If the assistant returns `[red]...[/red]` or similar, the TUI interprets it as markup rather than literal text. Headless output remains literal, so the display can diverge and content can be hidden/styled unintentionally. (`llm_do/ui/widgets/messages.py`)
- `LlmDoApp.CSS` defines `.assistant-message`, `.tool-call-message`, `.tool-result-message`, `.status-message`, `.approval-message` styles that are never used because widgets provide their own `DEFAULT_CSS` and never set those classes. This is dead CSS/overengineering and can mislead future edits. (`llm_do/ui/app.py`)
- `ApprovalMessage` and `MessageContainer.add_approval_request` are unused because `LlmDoApp` intercepts `ApprovalRequestEvent` and only shows the pinned `ApprovalPanel`, so approvals never show in scrollback. Other backends log approvals, so the TUI transcript is inconsistent. (`llm_do/ui/app.py`, `llm_do/ui/widgets/messages.py`, `llm_do/ui/events.py`)

## Open Questions
- For verbosity >= 2, should streaming output be inline (no newline per delta) with no final summary, or should the pipeline emit a final `TextResponseEvent` and keep deltas purely incremental?
- Should the TUI treat assistant/tool output as literal text (disable markup) to match headless output and avoid markup injection?
- Should approvals be logged in the message history (using `ApprovalMessage`) or is the pinned panel sufficient? If the panel remains, should the unused widget/CSS be removed?

## Conclusion
Review complete; items above are candidates for cleanup and alignment across backends.
