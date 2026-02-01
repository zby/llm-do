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
