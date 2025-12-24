# Examples and Docs Sweep Review

## Context
Review of examples and high-level docs for inconsistencies, outdated guidance, or unclear usage.

## Findings
- No current findings. Testing guidance is consistent (`uv run pytest`), and `docs/ui.md` now reflects the `UIEvent` + Textual approval flow.

## Analysis
- The main risk is future documentation drift as CLI and UI behavior evolves.

## Possible Fixes
- Keep README and `AGENTS.md` aligned when test commands or UI behavior change.

## Recommendations
1. Keep README and `AGENTS.md` aligned on test commands.
2. Re-verify `docs/ui.md` when UI output modes or flags change.

## Open Questions
- None.

## Conclusion
Docs drift remains the primary risk; regular sweep updates should keep examples and references current.
