# Task Completion Checklist
- Run tests: `.venv/bin/pytest` before committing (per AGENTS.md). Add focus flags if needed (e.g., `-k`, `-m examples`).
- If formatting/linting used: run `.venv/bin/black .` and `.venv/bin/ruff check .` when applicable.
- Review changes with `git diff` and avoid `git add -A`; stage specific files only. Write clear commit messages explaining why.
- Verify worker configs: sandboxes declared; tool_rules/approval settings appropriate; WorkerCreationDefaults leveraged instead of duplicate snippets.
- Ensure docs/readme or worker instructions updated if behavior changes. Keep workers focused; remove dead code.