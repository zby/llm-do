# Simplify: ui/formatting.py

## Context
Review of shared formatting helpers.

## Findings
- `truncate_lines()` truncates by length then by line count, which can lead to
  line-count output that is already truncated. If line count is the primary
  concern, consider truncating by lines first to simplify reasoning.
- Constants `TRUNCATION_SUFFIX` and `LINES_TRUNCATION_SUFFIX` are exported but
  only used internally; if external use is not needed, keep them private.
