# Simplify: toolsets/shell/

## Context
Review of shell toolset package (`execution.py`, `toolset.py`, `types.py`).

## Findings
- `ShellToolset.needs_approval()` and `get_capabilities()` both parse and
  validate the command, then match rules. A shared helper (e.g.,
  `parse_and_match()`) would remove duplication and keep behavior consistent.
- The package defines `ShellRule`/`ShellDefault` models but builtins pass raw
  dicts. Consider standardizing on the typed models (or drop them) to reduce
  unused abstraction.
- `check_metacharacters()` and `parse_command()` are always called together;
  a single `parse_command_or_block()` helper would simplify call sites.

## Open Questions
- Are typed rule models intended to be user-facing? If not, simplifying to
  plain dicts everywhere might be clearer.

## 2026-02-09 Review
- `ShellToolset.needs_approval()` and `ShellToolset.get_capabilities()` both parse command + rule matching; shared `analyze_command()` output would eliminate duplicate work.
- `match_shell_rules(command, args, ...)` ignores `command` beyond the signature; dropping the unused parameter would simplify API.
- `MAX_OUTPUT_BYTES` truncation is applied after UTF-8 decode via character length. Either rename to chars or enforce byte-based truncation consistently.
