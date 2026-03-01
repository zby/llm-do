# Simplify: ui/display.py

## Context
Review of display backend wrappers.

## Findings
- `RichDisplayBackend` and `HeadlessDisplayBackend` both implement the same
  streaming logic (delta vs full). Extract a shared helper or base class
  method to reduce duplication.
- `DisplayBackend.start()`/`stop()` default to no-ops; if most backends are
  no-op, consider making them optional or removing them to simplify the API.

## 2026-02-09 Review
- `RichDisplayBackend` and `HeadlessDisplayBackend` duplicate delta-vs-complete handling; shared base display helper could remove mirrored branches.
- `DisplayBackend.start/stop` default no-op methods could be a protocol instead of abstract base class unless lifecycle hooks are required.
