---
description: Why each configuration dimension was chosen — the reasoning behind initial system setup
category: derivation-rationale
created: 2026-02-16
status: active
---

# derivation rationale for llm-do

This knowledge system was derived for the llm-do project — an LLM orchestration runtime library under active development. The system integrates with an existing, well-structured project workspace rather than creating a greenfield vault.

## Key Design Decisions

**Moderate granularity** was chosen because the existing docs/notes/ and docs/adr/ files are per-topic explorations and decisions, not atomic claims. Each note covers a coherent design area (e.g., "dynamic agents runtime design", "tool output rendering semantics"). This matches how developers naturally write about their work.

**Hierarchical organization** preserves the existing directory structure: docs/notes/ with subcategories (research/, reviews/, agent-learnings/, meta/, archive/), docs/adr/ for formal decisions, and tasks/ with active/backlog/completed/recurring. The knowledge system adds self/ and ops/ alongside these without disrupting what works.

**Explicit linking** adds wiki links between internal workspace documents. This connects the dots that are currently implicit — when an ADR references a design exploration, or a task builds on a research note, those connections become navigable graph edges.

**Moderate processing** balances tracking with doing. The library is under active development; heavy academic processing would be overkill, but light tracking would miss the connections between design decisions that accumulate over months.

**3-tier navigation** provides hub → area indexes → individual notes. The existing subcategory structure in docs/notes/ maps naturally to area-level indexes.

**Full automation** leverages Claude Code hooks for session orientation, note validation, and session capture. The existing project already uses Claude Code extensively.

**Moderate schema** adds description and areas fields to internal workspace notes while leaving public documentation (docs/*.md) completely untouched. The existing convention of description-only frontmatter in docs/notes/ is preserved and extended.

## Boundary Decision

The critical design choice was the public/internal boundary:
- **Public** (docs/*.md directly): architecture.md, cli.md, reference.md, etc. — no knowledge system artifacts
- **Internal** (docs/notes/, docs/adr/, tasks/): enhanced with schema, wiki links, indexes
- **Agent memory** (self/): new, at project root
- **Operations** (ops/): new, at project root

This boundary respects the user's explicit requirement that public project documentation remain accessible without any knowledge about the knowledge system.

## Integration with Existing Systems

The existing tasks/ system (README.md, templates/, active/backlog/completed/recurring) is preserved as-is. The knowledge system's processing queue (ops/queue/) is separate — it handles knowledge processing tasks, not project tasks.

The existing docs/notes/README.md conventions (description frontmatter, subdirectories, archiving workflow) are preserved and extended rather than replaced.

---

Topics:
- [[methodology]]
