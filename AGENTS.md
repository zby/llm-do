# AGENTS.md — Field Guide for AI Agents

Key expectations that frequently trip up automation agents. See `README.md` for setup and usage.

---

## Key References

- `README.md` — setup, CLI usage, examples
- `docs/notes/archive/worker_delegation.md` — reference for worker hierarchies or delegation
- `docs/notes/` — working design documents and explorations (see Notes section)
- `examples/pitchdeck_eval/` — reference implementation for multi-worker patterns

---

## Development

- Run `.venv/bin/pytest` before committing (tests use dummy models, no live API calls)
- For executing python scripts use `.venv/bin/python` - the global environment does not have all dependencies
- Test worker features by creating example projects in `examples/` and running with `llm-do`
- Do not preserve backwards compatibility; with no external consumers, always prioritize cleaner design over keeping old behavior alive
- **YAGNI**: Don't implement features that aren't needed yet. If you identify a gap in the spec, create a note in `docs/notes/` instead of implementing it
- Favor clear architecture over hacks; delete dead code when possible
- If backcompat code is ever needed, mark it with `# BACKCOMPAT: <reason> - remove after <condition>` so it can be identified and removed later

---

## Worker Design

- Keep each worker focused on a single unit of work; use `worker_call` for sub-tasks
- Document available tools in `instructions` so models know how to call them
- Rely on `WorkerCreationDefaults` for shared defaults rather than copying YAML snippets

---

## Git Discipline

- **Never** `git add -A` — review `git status` and stage specific files
- Check `git diff` before committing

---

## Notes

- `docs/notes/` — working design documents, explorations, bug investigations
- Create notes to offload complex thinking that doesn't fit in a commit or TODO
- Include "Open Questions" section for unresolved decisions
- Move to `docs/notes/archive/` when resolved or implemented

---

Stay small, stay testable, trust the LLM.
