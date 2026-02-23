---
name: tasks-system
description: Manage the llm-do task tracker stored under tasks/ (backlog, active, completed, recurring) including creating new tasks, updating current state, moving tasks between stages, and applying the standard templates when planning or resuming work.
---

# llm-do Task Tracker

Use this skill whenever a request involves creating, editing, or reviewing work items in the `tasks/` directory. Tasks capture in-flight work for agents so they can pause/resume reliably.

## Directory Layout

- `tasks/backlog/` — lightweight ideas; use the backlog template.
- `tasks/active/` — scoped work currently in progress; follow the full active template.
- `tasks/completed/` — finished items (purge as needed; permanent learnings belong in docs/code).
- `tasks/recurring/` — periodic reviews/work; contains the recurring template.
- `tasks/templates/` — canonical templates for each task type.

Backlog entries may use `<slug>.md`; active and completed entries should use `<id>-<slug>.md` so IDs remain stable during edits.

## Standard Workflow

1. **Capture an idea**
   - Create `tasks/backlog/<slug>.md`.
   - Copy from `tasks/templates/backlog.md`.
   - Keep it short; only promote to active once ready.

2. **Activate a task**
   - Move the file into `tasks/active/`.
   - When promoting from backlog, rename to include an ID (for example `YYYYMMDD`): `tasks/backlog/foo.md` → `tasks/active/20260206-foo.md`.
   - Fill out every heading from `tasks/templates/active.md`: Status, Prerequisites (with checkboxes linking dependent tasks), Goal, Context (files, related work, verification plan), Decision Record (even if "none yet"), Tasks checklist, Current State narrative, Notes.
   - Frontload all context that can be gathered without changing code so implementation can start with minimal extra discovery.
   - Status is one of `information gathering`, `ready for implementation`, or `waiting for <dependency>`.

3. **Work / resume**
   - Before editing code, update **Prerequisites** and **Tasks** checkboxes to show the next actionable step.
   - Keep **Current State** fresh; treat it as the handoff note for the next agent session.
   - Log decisions inline. If a decision grows large or spans efforts, spin off a dedicated task and cross-link it.

4. **Complete**
   - When done, move the file to `tasks/completed/` (or delete if noise).
   - Replace open checkboxes with `[x]`.
   - Note merged PRs or docs in **Current State** or **Notes** for historical traceability.

5. **Recurring reviews**
   - For periodic audits (UI, security, etc.), create files in `tasks/recurring/` using `tasks/templates/recurring.md`.
   - Treat recurring task files as stable runbooks: do not update checklist state or add per-run history in the task file.
   - Record each run in the output note (for example `docs/notes/reviews/review-<area>.md`) by appending a dated section with findings and follow-ups.
   - Edit recurring task files only when the review scope/process changes.

## Templates

Canonical templates live in `tasks/templates/`:

- [`templates/backlog.md`](templates/backlog.md)
- [`templates/active.md`](templates/active.md)
- [`templates/recurring.md`](templates/recurring.md)

## Task Review

When asked to review a task, carefully analyze the task file and propose revisions for:

- **Goal clarity** — Is the goal well-defined and achievable?
- **Scope** — Should it be split, expanded, or narrowed?
- **Architecture** — Better technical approach, cleaner design
- **Missing steps** — Gaps in the Tasks checklist
- **Prerequisites** — Unidentified dependencies or blockers
- **Frontloading boundary** — Is pre-implementation research captured? Are code-changing probes correctly treated as execution or prerequisite tasks?
- **Verification** — Is "How to verify" concrete and testable?
- **Risk/edge cases** — Failure modes not yet considered

**Resolve open questions:** Identify questions the task creator left unaddressed or assumptions that need validation. Research available sources (codebase, docs, web) to answer them rather than just flagging them.

For each proposed change, provide:
1. **What** — The specific change being proposed
2. **Why** — Detailed rationale and justification
3. **Trade-offs** — Any downsides or costs to consider
4. **Priority** — Must-have vs nice-to-have

Focus on substantive improvements. Challenge assumptions and identify gaps.

## Authoring Guidelines

- Keep each task to a single coherent goal; split unrelated efforts.
- **Inline information from notes** — When creating a task based on a note or design doc, copy the relevant content directly into the task rather than just referencing it (e.g., "see `docs/notes/foo.md`"). Reading an additional file is extra work for the implementer; frontload that effort when writing the task.
- **Self-contained tasks** — Aim for the full task implementation to fit within one context window. When you know the implementer will need specific background information, inline it rather than making them go find it.
- **Frontload aggressively, but only with no-code research** — Include current behavior mapping, impacted files/symbols, constraints, assumptions, risks, and clear verification steps when these can be established without modifying code.
- **Treat code-changing probes as execution work** — If validating an assumption requires code changes, runtime mutation, or experiments that alter behavior, do not treat it as frontloaded research.
- **Promote substantial probes into prerequisite tasks** — When a probe can materially change scope, architecture, or estimates, create a separate prerequisite task and block the implementation task on it.
- **Keep small probes inline when tightly scoped** — If the probe is minor and does not change task boundaries, keep it in the task checklist rather than splitting it out.
- **Recurring tasks are reusable runbooks** — Keep recurring task files stable across runs so output is comparable over time; store run-by-run results in notes/review docs, not in `tasks/recurring/*.md`.
- Add links to relevant files (`path/to/file.py`) and related tasks so agents can `rg` quickly.
- Always state **How to verify** within Context.
- Prefer `Prerequisites: none` unless genuinely blocked.
- Notes capture gotchas encountered during execution; migrate durable learnings to `AGENTS.md`, inline code comments, or docs afterward.
- Completed tasks are not documentation — if a decision matters broadly, extract it to docs before archiving.

## Frontloading vs Prerequisite Probe Tasks

Use this decision rule when authoring tasks:

1. If information can be gathered from reading code/docs/history only, frontload it into the task now.
2. If checking an assumption requires changing code or running behavior-altering experiments, treat it as execution work.
3. If that execution work can significantly affect plan/scope, split it into a prerequisite task and link it in **Prerequisites**.
4. If the execution work is small and low-risk, keep it as an explicit early checklist item in **Tasks**.
5. If task authoring reveals small, low-risk improvements to existing code (e.g., a missing guard, a clearer name, a stale comment), propose them to the user directly rather than writing a separate task.

## Helpful Commands

- `rg -n "<Task Name>" tasks/` — find all references to a task ID/slug.
- `mv tasks/backlog/foo.md tasks/active/20260206-foo.md` — promote backlog to active and assign a stable ID.
- `rg -L "^## Prerequisites$" tasks/active/*.md` — find active tasks missing a **Prerequisites** section.
- `rg -n "^- \\[ \\] none$" tasks/active/*.md` — find tasks where `none` is still unchecked.
