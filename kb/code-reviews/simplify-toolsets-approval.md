# Simplify: toolsets/approval.py

## Context
Review of approval config helpers for toolsets.

## Findings
- `get_toolset_approval_config()` and `set_toolset_approval_config()` are thin
  wrappers around `getattr`/`setattr`. If this pattern is stable, consider
  moving the config onto a dataclass field on toolsets that need it instead of
  using a magic attribute name.
- `TOOLSET_APPROVAL_ATTR` is a hidden convention. If external users should not
  rely on it, consider keeping these helpers private and exposing a clearer
  runtime API.

## 2026-02-09 Review
- `TOOLSET_APPROVAL_ATTR` remains magic-string metadata; if approval config becomes common, an explicit typed wrapper would reduce hidden conventions.
- `get_toolset_approval_config()` and `set_toolset_approval_config()` are minimal attribute accessors; they can be folded into runtime approval wrapping if external use is not required.
