---
description: Types are structural contracts on individual documents; directories are organizational grouping. Neither depends on the other — a document's type doesn't change when it moves between directories.
type: note
traits: [has-claim]
status: seedling
areas: [claw-design]
---

# Types and directories are orthogonal

Types assert structural properties of individual documents — what sections are expected, what metadata is required, what's checkable. Directories group documents by topic, lifecycle, provenance, or whatever convention the user finds useful. These are independent axes.

A task in `tasks/active/` has `type: task` defining its structure (Goal, Tasks checklist, Current State). The `active/` directory tells you its lifecycle stage. Moving it to `completed/` changes the lifecycle signal without changing its type or structure.

A `note` with `has-claim` works identically whether it lives in `notes/`, `notes/related-systems/`, or `notes/agent-learnings/`. The directory carries provenance or topic grouping; the type carries structural expectations.

## Why this matters

If types depended on directories, you'd need to redefine types whenever someone creates a new subdirectory. If directories encoded type information, you'd lose the freedom to organise by whatever dimension matters — topic, lifecycle, provenance, project area.

The [document classification](./document-classification.md) system should work across any directory structure. Validation, search, and linking operate on individual documents via frontmatter, not on directory conventions. Directory-level conventions (like `tasks/active/` meaning "in progress") are useful additions but not part of the type system.

## Current stance

This separation is the simpler default — it avoids coupling two concerns before we understand either well enough. It may change if we find strong arguments for directory-type integration (e.g. if directory conventions consistently predict type, or if type-per-directory reduces configuration burden). For now, keeping them independent means fewer assumptions to undo.

Directory-based subsystems like `tasks/` (with `backlog/`, `active/`, `completed/`) do duplicate what the type system could express — lifecycle stage is effectively a status field. But tasks are a small, self-contained subsystem with their own README and conventions. Coupling it to the whole type system just to eliminate that duplication would add complexity to both for minimal gain. Small subsystems can afford local conventions that don't need to integrate with the global design.

## Implications

- `/validate` and validation scripts should work recursively across subdirectories
- `sync_topic_links.py` should handle notes in any subdirectory (already does)
- People should be free to create subdirectories without needing to register them as types or areas
- Directory-based conventions (lifecycle, grouping) are documented per-directory (e.g. `tasks/README.md`) not in the type system
