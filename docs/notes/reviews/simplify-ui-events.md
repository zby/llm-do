# Simplify: ui/events.py

## Context
Review of UI event classes and rendering helpers.

## Findings
- Many events duplicate render logic between `render_text()` and
  `render_rich()`. A small helper per event (or mixins) could reduce
  duplication and keep formatting consistent.
- `TextResponseEvent` encodes three states (start, delta, complete) in one
  class, leading to branching in renderers. Consider separate event types for
  start/delta/complete to simplify logic.
- `agent_tag` always formats `[agent:depth]` even when agent is empty. A
  guard could avoid noisy tags in headless output.
