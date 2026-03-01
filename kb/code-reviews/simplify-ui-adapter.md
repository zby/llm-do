# Simplify: ui/adapter.py

## Context
Review of runtime-event to UI-event adapter.

## Findings
- Tool call/result adaptation and args JSON logic is duplicated between this
  adapter and UI widgets. Consider a shared helper for args formatting so
  tool calls render consistently in text + TUI.
- `adapt_event()` has a long if/elif chain. A dispatch table keyed by event
  type could simplify control flow and make it easier to add new events.

## 2026-02-09 Review
- `adapt_event()` remains a long `isinstance` chain with repeated envelope fields (`agent`, `depth`); using per-event handler registry would reduce branching.
- Tool call/result adapters duplicate `getattr` fallback patterns and can share small extraction helpers.
- Runtime-to-UI mapping is now stable; remaining simplification is structural rather than behavioral.
