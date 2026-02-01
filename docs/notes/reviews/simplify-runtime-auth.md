# Simplify: runtime/auth.py

## Context
Review of auth configuration types shared by runtime.

## Findings
- `AuthMode` is a single `Literal` alias. If it is only referenced in one or
  two places, consider inlining it where used to avoid a one-line module.
- If `AuthMode` is intended to be public API, consider grouping it with other
  runtime config types (e.g., in `runtime/manifest.py`) to reduce file count.
