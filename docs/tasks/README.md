# Tasks

Operational documents for tracking work in progress.

## Purpose

1. **Recovery** - After crash/context loss, AI reads task and resumes work
2. **Scoping** - Break work into chunks that fit in context window
3. **Dependencies** - Track what must be done first
4. **Bootstrap** - Capture key context (files, commands, links) so work can start immediately

## Directories

| Directory | Purpose |
|-----------|---------|
| `active/` | Work in progress or planned next |
| `backlog/` | Ideas worth tracking, not yet planned |
| `completed/` | Finished work (can be purged periodically) |

## Usage

- **New idea**: Create in `backlog/` with lightweight template
- **Planning work**: Move from `backlog/` to `active/`, flesh out full template
- **Starting work**: Create task in `active/`
- **Resuming work**: Read task, continue from current state
- **Finishing work**: Move to `completed/` or delete

Completed tasks can be purged periodically - permanent decisions belong in AGENTS.md, code comments, or other documentation.

## Backlog Template

```markdown
# Feature Name

## Idea
What this would do.

## Why
Why it might be valuable.

## Rough Scope
High-level bullets of what's involved.

## Why Not Now
What's blocking or why it's not a priority.

## Trigger to Activate
What would make this worth doing.
```

## Active Task Template

```markdown
# Task Name

## Prerequisites
- [ ] other-task-name (dependency on another task)
- [ ] design decision needed (new design / approval)
- [ ] none

## Goal
One sentence: what "done" looks like.

## Context
- Relevant files/symbols:
- Related tasks/notes/docs:
- How to verify / reproduce:

## Tasks
- [x] completed step
- [ ] next step
- [ ] future step

## Current State
Where things stand right now. Update as work progresses.

## Notes
- Short observations, gotchas, things tried
- Reference external docs for longer explanations
```

## Guidelines

- Keep tasks focused - one coherent unit of work
- Front-load background gathering so tasks are startable without extra research
- Prefer `Prerequisites: none` unless blocked by new design or another task
- Update current state frequently
- Notes prevent repeating mistakes after recovery
- Delete or archive when done - this is not documentation
