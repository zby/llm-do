# Simplify: toolsets/loader.py

## Context
Review of toolset spec resolution/instantiation helpers.

## Findings
- `instantiate_toolsets()` is a simple loop that could be a list
  comprehension; if it is only used once, consider inlining to reduce
  indirection.
- `resolve_toolset_specs()` does not deduplicate toolset names; if duplicates
  are not allowed, consider validating and surfacing a clearer error.

## 2026-02-09 Review
- This module is now pure compatibility re-export. If no external callers depend on `llm_do.toolsets.loader`, removing it and updating imports would reduce indirection.
- If compatibility is still needed, mark this file as backcompat-only and keep the surface minimal.
