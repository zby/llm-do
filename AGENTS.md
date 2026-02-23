# AGENTS.md — Field Guide for AI Agents

Key expectations that frequently trip up automation agents. See `README.md` for setup and usage.

---

## Key References

- `README.md` — setup, CLI usage, examples
- `docs/architecture.md` — internal design, agent delegation, approval system
- `project_claw/notes/` — working design documents and explorations (see Notes section)
- `examples/pitchdeck_eval/` — reference implementation for multi-agent patterns

---

## Development
- For executing python scripts use `.venv/bin/python` - the global environment does not have all dependencies
- Test agent features by creating example projects in `examples/` and running with `llm-do`
- Do not preserve backwards compatibility; with no external consumers, always prioritize cleaner design over keeping old behavior alive
- **YAGNI**: Don't implement features that aren't needed yet. If you identify a gap in the spec, create a note in `project_claw/notes/` instead of implementing it
- Favor clear architecture over hacks; delete dead code when possible
- If backcompat code is ever needed, mark it with `# BACKCOMPAT: <reason> - remove after <condition>` so it can be identified and removed later

---

## Agent Design

- Keep each agent focused on a single unit of work; use `call_agent` for sub-tasks
- Document available tools in `instructions` so models know how to call them

---

## Architecture & Design Discussions

When working on code architecture, interface design, or system modeling, act as a **full research collaborator** rather than a terse advisor. This means:

- Speak at length about design trade-offs, alternatives considered, and reasoning
- Surface your own concerns, hunches, and open questions proactively
- Engage with the human's ideas critically — push back, extend, or redirect as needed
- Share and probe mental models — how you conceptualize the system, where the boundaries are, what analogies inform your thinking
- Treat the conversation as joint exploration, not Q&A

This collaborative mode applies to: runtime design, API boundaries, data flow, abstraction choices, naming conventions, and similar structural decisions. For routine implementation tasks, the standard concise style remains appropriate.

---

## Quality Checks

Run relevant checks before submitting changes:
- **Lint**: `uv run ruff check .`
- **Typecheck**: `uv run mypy llm_do`
- **Tests**: `uv run pytest` — all tests must pass. Tests use dummy models, no API calls needed.
- **Inline snapshots**: when changing `snapshot(...)` assertions, run `uv run pytest <target> --inline-snapshot=fix` and review rewritten diffs before final test runs.

**Never claim checks passed unless they were actually run.** If checks cannot be run, explicitly state why.

---

## Git Discipline

- **Never** `git add -A` — review `git status` and stage specific files
- Check `git diff` before committing
- **Never** use `git reset --hard` or force-push without explicit permission
- Prefer safe alternatives: `git revert`, new commits, temporary branches

---

## Notes

- `project_claw/notes/` — working design documents, explorations, bug investigations
- Create notes to offload complex thinking that doesn't fit in a commit or TODO
- Include "Open Questions" section for unresolved decisions
- Delete when resolved or no longer relevant

---

## Tasks & Notes Workflow (Ticketing System)

**Always** read the relevant README before working with tasks or notes (create, edit, resume, move, or close):
- `project_claw/tasks/README.md` for tasks
- `project_claw/notes/README.md` for notes

### Tasks
- Use `project_claw/tasks/active/` for in-progress work; follow the task template and keep "Current State" updated.
- Keep tasks scoped to one coherent unit; track prerequisites and dependencies explicitly.
- When finished, move the task to `project_claw/tasks/completed/` or delete it (completed tasks are not documentation).

### Notes
- Use `project_claw/notes/` for explorations and reasoning that doesn’t belong in code or tasks; follow the note template.
- Include "Open Questions" for unresolved items; delete when resolved.

---

## Agent Self-Improvement

See "When to Write a Note" in `CLAUDE.md` for the full policy. Agent-initiated notes go to `project_claw/notes/agent-learnings/` — notes only, no tasks or ADRs.

---

Stay small, stay testable, trust the LLM.
