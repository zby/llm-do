# Tasks

Operational documents for tracking work in progress.

## Purpose

1. **Recovery** - After crash/context loss, AI reads task and resumes work
2. **Scoping** - Break work into chunks that fit in context window
3. **Dependencies** - Track what must be done first

## Usage

- **Starting work**: Create task in `active/`
- **Resuming work**: Read task, continue from current state
- **Finishing work**: Move to `completed/` or delete

Completed tasks can be purged periodically - permanent decisions belong in AGENTS.md, code comments, or other documentation.

## Task Template

```markdown
# Task Name

## Prerequisites
- [ ] other-task-name (if dependent on another task)
- [ ] specific condition that must be true before starting

## Goal
One sentence: what "done" looks like.

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
- Update current state frequently
- Notes prevent repeating mistakes after recovery
- Delete or archive when done - this is not documentation
