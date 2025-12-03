# AGENTS.md — Field Guide for AI Agents

Key expectations that frequently trip up automation agents. See `README.md` for setup and usage.

---

## Key References

- `README.md` — setup, CLI usage, examples
- `docs/worker_delegation.md` — read when implementing worker hierarchies or delegation
- `docs/worker_pitfalls.md` — read before creating or modifying workers
- `examples/pitchdeck_eval/` — reference implementation for multi-worker patterns

---

## Development

- Run `.venv/bin/pytest` before committing (tests use dummy models, no live API calls)
- For executing python scripts use `.venv/bin/python` - the global environment does not have all dependencies
- Prefer creating/editing workers via `workers/*.worker` and run them with `llm-do`
- Do not preserve backwards compatibility; with no external consumers, always prioritize cleaner design over keeping old behavior alive
- Favor clear architecture over hacks; delete dead code when possible
- If backcompat code is ever needed, mark it with `# BACKCOMPAT: <reason> - remove after <condition>` so it can be identified and removed later

---

## Worker Design

- Keep each worker focused on a single unit of work; use `worker_call` for sub-tasks
- Declare sandboxes explicitly with the minimal access needed
- Document available tools in `instructions` so models know how to call them
- Rely on `WorkerCreationDefaults` for shared defaults rather than copying YAML snippets

---

## Git Discipline

- **Never** `git add -A` — review `git status` and stage specific files
- Check `git diff` before committing
- Write clear commit messages (why, not just what)

---

Stay small, stay testable, trust the LLM.
