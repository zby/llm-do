# AGENTS.md — Field Guide for AI Agents

Key expectations that frequently trip up automation agents. See `README.md` for setup and usage.

---

## Key References

- `README.md` — setup, CLI usage, examples
- `docs/worker_delegation.md` — how `worker_call`/`worker_create` behave
- `examples/pitchdeck_eval/` — end-to-end multi-worker example

---

## Development

- Run `.venv/bin/pytest` before committing (tests use dummy models, no live API calls)
- For executing python scripts use `.venv/bin/python` - the global environment does not have all dependencies
- Prefer creating/editing workers via `workers/*.yaml` and run them with `llm-do`
- Style: black, 4 spaces, snake_case/PascalCase
- No backwards compatibility promise—breaking changes are fine if they improve design
- Favor clear architecture over hacks; delete dead code when possible

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

## Common Pitfalls

- Forgetting to configure sandboxes leads to runtime `KeyError`
- Approval rules default to auto-approve; lock down `tool_rules` for critical workers
- Model inheritance is worker → caller → CLI flag; set `model` in YAML if a worker needs a specific model


---

Stay small, stay testable, trust the LLM.
