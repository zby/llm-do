# Simplify: ui/formatting.py

## Context
Review of shared formatting helpers.

## Findings
- `truncate_lines()` truncates by length then by line count, which can lead to
  line-count output that is already truncated. If line count is the primary
  concern, consider truncating by lines first to simplify reasoning.
- Constants `TRUNCATION_SUFFIX` and `LINES_TRUNCATION_SUFFIX` are exported but
  only used internally; if external use is not needed, keep them private.

## 2026-02-09 Review
- `truncate_text()` appends suffix after `max_len` slicing, so returned value can exceed `max_len`; either enforce hard cap including suffix or rename parameter to clarify behavior.
- `truncate_lines()` truncates by chars first then by lines, which can produce non-intuitive output ordering. A single truncation policy order would simplify reasoning.
