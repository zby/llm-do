# Simplify: ui/parser.py

## Context
Review of UI parsing helpers.

## Findings
- `parse_approval_request()` always sets `agent="agent"`. If the caller
  knows the agent, pass it in as an argument to avoid a hard-coded value.
- The module is a single function; consider moving it into the adapter or
  approval workflow to reduce file count.

## 2026-02-09 Review
- `parse_approval_request()` is a thin `getattr` wrapper and can be inlined into `ui/runner.py` unless this module is expected to grow additional parsers.
