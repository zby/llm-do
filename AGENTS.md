# AGENTS.md — Field Guide for AI Agents

Key expectations that frequently trip up automation agents. See `README.md` for setup and usage.

---

## Key References

- `README.md` — setup, CLI usage, examples
- `docs/worker_delegation.md` — reference for worker hierarchies or delegation
- `docs/notes/` — working design documents and explorations (see Notes section)
- `examples/pitchdeck_eval/` — reference implementation for multi-worker patterns

---

## Development
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

- **Run tests before every commit**: `uv run pytest` — all tests must pass before committing. Tests use dummy models, no API calls needed.
- **Never** `git add -A` — review `git status` and stage specific files
- Check `git diff` before committing

---

## Notes

- `docs/notes/` — working design documents, explorations, bug investigations
- Create notes to offload complex thinking that doesn't fit in a commit or TODO
- Include "Open Questions" section for unresolved decisions
- Move to `docs/notes/archive/` when resolved or implemented

---

## Tasks & Notes Workflow (Ticketing System)

**Always** read the relevant README before working with tasks or notes (create, edit, resume, move, or close):
- `docs/tasks/README.md` for tasks
- `docs/notes/README.md` for notes

### Tasks
- Use `docs/tasks/active/` for in-progress work; follow the task template and keep "Current State" updated.
- Keep tasks scoped to one coherent unit; track prerequisites and dependencies explicitly.
- When finished, move the task to `docs/tasks/completed/` or delete it (completed tasks are not documentation).

### Notes
- Use `docs/notes/` for explorations and reasoning that doesn’t belong in code or tasks; follow the note template.
- Include "Open Questions" for unresolved items; move to `docs/notes/archive/` when resolved.
- Archived notes are immutable — do not edit content after archiving.

---

Stay small, stay testable, trust the LLM.
