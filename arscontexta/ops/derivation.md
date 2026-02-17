---
description: How this knowledge system was derived — enables architect and reseed commands
created: 2026-02-16
engine_version: "0.8.0"
---

# System Derivation

## Configuration Dimensions

| Dimension | Position | Conversation Signal | Confidence |
|-----------|----------|--------------------|--------------------|
| Granularity | Moderate | Per-entry design notes, ADRs, task files — existing structure is per-topic | HIGH |
| Organization | Hierarchical | Existing docs/notes/ subcategories, docs/adr/, tasks/ hierarchy | HIGH |
| Linking | Explicit | "can have additional structures" for internal workspace; wiki links between notes, ADRs, tasks | HIGH |
| Processing | Moderate | "track" suggests retrieval; existing research/ subfolder and design notes show analytical work | MEDIUM |
| Navigation | 3-tier | Existing multi-level hierarchy (hub → categories → notes), moderate volume | MEDIUM |
| Maintenance | Condition-based | Default — appropriate for evolving library codebase | Default |
| Schema | Moderate | Internal docs get frontmatter; public docs (docs/*.md) stay clean | HIGH |
| Automation | Full | Claude Code platform; user confirmed arscontexta/self/ and arscontexta/ops/ placement | HIGH |

## Personality Dimensions

| Dimension | Position | Signal |
|-----------|----------|--------|
| Warmth | neutral-helpful | default |
| Opinionatedness | neutral | default |
| Formality | professional | software development context |
| Emotional Awareness | task-focused | default |

## Vocabulary Mapping

| Universal Term | Domain Term | Category |
|---------------|-------------|----------|
| notes | docs/notes | folder |
| inbox | inbox | folder |
| archive | archive | folder |
| note (type) | note | note type |
| reduce | extract | process phase |
| reflect | connect | process phase |
| reweave | revisit | process phase |
| verify | review | process phase |
| validate | validate | process phase |
| rethink | rethink | process phase |
| MOC | index | navigation |
| description | description | schema field |
| topics | areas | schema field |
| topic map | index | navigation |
| pipeline | pipeline | process |
| wiki link | link | linking |
| thinking notes | notes | content |
| arscontexta/self/ space | project memory | space |
| orient | orient | session phase |
| persist | persist | session phase |
| inbox | inbox | folder |
| archive | docs/notes/archive | folder |

## Platform

- Tier: Claude Code
- Automation level: full
- Automation: full (default)

## Active Feature Blocks

- [x] wiki-links — always included (kernel)
- [x] maintenance — always included (always)
- [x] self-evolution — always included (always)
- [x] session-rhythm — always included (always)
- [x] templates — always included (always)
- [x] ethical-guardrails — always included (always)
- [x] processing-pipeline — always included (always)
- [x] schema — always included (always)
- [x] helper-functions — always included (always)
- [x] graph-analysis — always included (always)
- [x] methodology-knowledge — always included (always)
- [ ] atomic-notes — excluded: granularity is moderate (per-entry)
- [x] mocs — included: 3-tier navigation for existing hierarchy
- [ ] semantic-search — excluded: not active initially, can add via qmd later
- [x] self-space — included: arscontexta/self/ confirmed at project root
- [ ] multi-domain — excluded: single project
- [ ] personality — excluded: default neutral-helpful

## Coherence Validation Results

- Hard constraints checked: 3. Violations: none
- Soft constraints checked: 7. Auto-adjusted: none. User-confirmed: none
- Compensating mechanisms active: none needed

## Failure Mode Risks

1. **Productivity Porn** (HIGH) — meta-work on knowledge system displaces library development
2. **Temporal Staleness** (HIGH) — design notes become outdated as library evolves
3. **Collector's Fallacy** (HIGH) — accumulating explorations without distilling into decisions/ADRs
4. **Orphan Drift** (MEDIUM) — notes created but never connected to indexes or other notes

## Domain Context

This is a knowledge system for tracking design notes, architecture decisions, and tasks during active library development (llm-do — an LLM orchestration runtime). The system integrates with existing conventions:

- **Public docs** (docs/*.md): architecture.md, cli.md, reference.md, etc. — untouched by the knowledge system
- **Internal workspace** (docs/notes/, docs/adr/, tasks/): enhanced with optional schema, wiki links, and indexes
- **Existing task system** (tasks/): mature active/backlog/completed/recurring workflow — preserved as-is
- **Existing note conventions** (docs/notes/README.md): description frontmatter, subdirectories for categories

## Extraction Categories

1. **Design decisions** — architecture choices, trade-offs, rationale → ADR or note
2. **Technical insights** — learnings about implementation patterns → note
3. **API design** — interface decisions and user experience considerations → note
4. **Integration patterns** — how components interact → note
5. **Open questions** — things to explore or decide later → task or note

## Generation Parameters

- Folder names: docs/notes/ (existing), docs/adr/ (existing), tasks/ (existing), arscontexta/self/ (new), arscontexta/ops/ (new), arscontexta/inbox/ (new), arscontexta/templates/ (new), arscontexta/manual/ (new)
- Skills to generate: 16 — vocabulary-transformed
- Hooks to generate: orient, capture, validate, commit
- Templates to create: note.md, adr.md, index.md, observation.md
- Topology: single-agent (Claude Code)
