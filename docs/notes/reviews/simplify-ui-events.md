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

## 2026-02-09 Review
- Event classes still combine three concerns (`render_text`, `render_rich`, `create_widget`), creating a wide and duplicated surface.
- Tool call/result formatting logic is duplicated with `ui/widgets/messages.py`; choose one formatter source and reuse in both render paths.
- `truncate_text` may exceed requested max length because suffix is appended after hard cut. Decide whether max length should include suffix and centralize policy.
