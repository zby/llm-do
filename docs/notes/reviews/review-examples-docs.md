# Examples and Docs Sweep Review

## Context
Review of examples and high-level docs for inconsistencies, outdated guidance, or unclear usage.

## Findings
- `README.md` instructs "Run uv run pytest" before committing, while `AGENTS.md` requires `.venv/bin/pytest`; guidance conflicts and can confuse contributors.
- `docs/ui.md` references Rich output paths that no longer exist (see UI review), which makes the docs/example narrative inconsistent with the current default Textual TUI.

## Analysis
- Conflicting test commands encourage contributors to run the wrong environment, leading to missing deps or inconsistent failures. The AGENTS guidance should be the single source of truth.
- UI docs drift makes the UI feel unstable and undermines confidence in examples; it also increases support burden because users follow stale instructions.

## Possible Fixes
- Testing guidance:
  - Align README to `.venv/bin/pytest` (per AGENTS), or
  - Update AGENTS to match README if the project prefers `uv run pytest`.
- UI docs:
  - Update `docs/ui.md` to describe the Textual backend and approval events, or
  - Consolidate UI docs into a single location and link from README to reduce drift.

## Recommendations
1. Make README match `AGENTS.md` by defaulting to `.venv/bin/pytest`.
2. Update `docs/ui.md` to reflect the Textual TUI and current event flow.
3. Add a short "source of truth" note in README or AGENTS to prevent future drift.

## Open Questions
- Which testing command should be the single source of truth: `uv run pytest` or `.venv/bin/pytest`?
- Should UI docs be consolidated under the same source (README vs docs) to avoid drift?

## Conclusion
Docs drift is the main risk: align testing guidance and refresh UI documentation to match current behavior, then centralize ownership so future updates are consistent.
