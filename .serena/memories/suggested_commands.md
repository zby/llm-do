# Suggested Commands
- Install editable: `pip install -e .`
- Run CLI example: `cd examples/greeter; llm-do greeter "Tell me a joke" --model $MODEL`
- Run workers generally: `llm-do <worker_name> "input" --model $MODEL [--attachments <paths>]`
- Tests (per AGENTS.md): `.venv/bin/pytest` (uses dummy models; suite ignores tests/test_integration_live.py by default). Focus examples only: `.venv/bin/pytest -m examples`.
- Python scripts: `.venv/bin/python path/to/script.py`
- Formatting/lint (available via optional deps): `.venv/bin/black .`; `.venv/bin/ruff check .` (if installed).
- PowerShell filesystem basics (Windows): `Get-ChildItem` (ls), `Get-Content file` (cat), `Set-Location path` (cd), `Select-String -Pattern "text" -Path file` (grep-like).