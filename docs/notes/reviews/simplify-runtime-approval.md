# Simplify: runtime/approval.py

## Context
Review of approval policy wiring and toolset wrappers.

## Findings
- `make_headless_approval_callback()` and `make_tui_approval_callback()` both
  implement approve_all/reject_all guards. Consider a shared helper to remove
  duplicated logic and keep decisions consistent.
- `ApprovalDeniedResultToolset` wraps `ApprovalToolset` solely to translate
  `PermissionError` to a dict. If `ApprovalToolset` can surface a structured
  permission error directly, the extra wrapper could be removed.
- `_default_cache_key()` and `_ensure_decision()` are tiny helpers used only in
  this module; consider inlining to reduce indirection unless reuse grows.

## Open Questions
- Should permission errors be part of the approval toolset contract instead of
  a separate wrapper (`ApprovalDeniedResultToolset`)?

## 2026-02-09 Review
- `make_headless_approval_callback()` and `make_tui_approval_callback()` both enforce approve/reject exclusivity and mode branching; shared normalization of mode flags would reduce duplicate guards.
- `resolve_approval_callback()` still uses implicit deny behavior for prompt mode without callback; making that policy explicit at call sites would reduce hidden defaults.
- `ApprovalDeniedResultToolset` remains a translation wrapper around `PermissionError`; if upstream toolset behavior can return structured denial payloads, this wrapper can disappear.
