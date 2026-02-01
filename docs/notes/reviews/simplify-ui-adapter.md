# Simplify: ui/adapter.py

## Context
Review of runtime-event to UI-event adapter.

## Findings
- Tool call/result adaptation and args JSON logic is duplicated between this
  adapter and UI widgets. Consider a shared helper for args formatting so
  tool calls render consistently in text + TUI.
- `adapt_event()` has a long if/elif chain. A dispatch table keyed by event
  type could simplify control flow and make it easier to add new events.
