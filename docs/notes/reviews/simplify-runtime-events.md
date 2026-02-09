# Simplify: runtime/events.py

## Context
Review of runtime event envelope types.

## Findings
- `UserMessageEvent` is a tiny wrapper around a string and is only used once in
  `Runtime.run_entry()`. Consider inlining that into `RuntimeEvent` as a
  sentinel type (e.g., `event_kind`) to reduce the number of event classes.
- `RuntimeEvent` is effectively a simple tuple of (agent, depth, event). If
  event emission always uses the same fields, consider a NamedTuple or a small
  helper function to reduce boilerplate.

## Open Questions
- Do we expect more system events beyond `UserMessageEvent`? If not, a simpler
  representation might be sufficient.

## 2026-02-09 Review
- `RuntimeEvent` and `UserMessageEvent` remain minimal wrappers. If no additional system-event variants are expected, a simpler tagged payload shape could replace the extra class.
- Event envelope creation is repeated at call sites; a tiny constructor helper (e.g., `user_message_event(agent, depth, content)`) would reduce boilerplate.
