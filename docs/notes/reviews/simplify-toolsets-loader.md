# Simplify: toolsets/loader.py

## Context
Review of toolset spec resolution/instantiation helpers.

## Findings
- `instantiate_toolsets()` is a simple loop that could be a list
  comprehension; if it is only used once, consider inlining to reduce
  indirection.
- `resolve_toolset_specs()` does not deduplicate toolset names; if duplicates
  are not allowed, consider validating and surfacing a clearer error.
