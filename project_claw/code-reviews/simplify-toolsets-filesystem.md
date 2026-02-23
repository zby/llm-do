# Simplify: toolsets/filesystem.py

## Context
Review of filesystem toolset behavior and approval logic.

## Findings
- `read_file()` computes `total_chars` by reading the remainder of the file.
  If the value is not essential, consider dropping it or using file size to
  avoid a second full read.
- `call_tool()` is a manual if/elif chain for three methods. A small dispatch
  map could reduce branching and make new tools easier to add.
- `get_capabilities()` and `needs_approval()` both resolve paths and check
  base-path relations. A shared helper could reduce duplicated path handling.

## Open Questions
- Do callers rely on `total_chars`, or can it be removed to simplify reads?

## 2026-02-09 Review
- `read_file()` has separate small-file and streaming branches with partially duplicated truncation accounting; one streaming path for all sizes would simplify behavior.
- `call_tool()` and `get_tools()` switch on explicit tool names; declarative dispatch tables (name -> function/schema/description) would remove repeated branching.
- Path capability classification (`within_base`/`outside_base`) is computed but writes are not blocked outside base path by default; if containment is desired, enforce it in `_resolve_path` to remove policy ambiguity.
