# Project Claw

A [Claw](./sources/simon-willison-karpathy-claws.md) — a personal AI-assisted system that evolves with use — for llm-do's design history. Also a live example of the crystallisation pattern it documents.

## Why this exists

**We need it.** llm-do's design evolves across sessions. Without persistent notes, decisions, and indexes, every session starts cold. Project Claw captures what we learn so we can build on it.

**It showcases crystallisation.** A knowledge base for a project must evolve with that project — exactly the stabilise/soften cycle described in `docs/theory.md`. Notes start as freeform LLM-written explorations (soft), patterns get extracted into templates and indexes (stabilised), and when requirements shift, rigid structures get rethought (softened again). The KB itself follows the crystallisation gradient it documents.

## Current runtime: Claude Code

We prototype this system using Claude Code and Opus via subscription. Running Opus through the API would be too expensive for the volume of knowledge work involved. So for now, the KB operates on Claude Code's machinery: CLAUDE.md instructions, `.claude/skills/`, markdown files, and ripgrep queries.

The plan is to progressively port tooling to llm-do — search, connection-finding, health checks — as the patterns stabilise. This is itself crystallisation: what starts as LLM judgment guided by prose instructions becomes deterministic code as we learn what works. Eventually `project_claw/` moves to `examples/project_claw/` as a working example.

## Structure

```
project_claw/
  notes/          — design notes, explorations, insights
  adr/            — architecture decision records
  sources/        — snapshots of external references
  kb-design/      — notes about the KB system itself
  tasks/          — task tracker (backlog, active, completed, recurring)
  templates/      — writing scaffolds for all content types
  indexes.md      — directory of topic indexes
  WRITING.md      — detailed guide for creating and editing content
```

See `CLAUDE.md` in the repo root for the routing table and search patterns.
