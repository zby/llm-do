# Project Claw

A [Claw](./sources/simon-willison-karpathy-claws.md) — an AI-assisted system that accumulates context and evolves with use — scoped to the llm-do project. Also a live example of the crystallisation pattern it documents.

## Why this exists

**The memory is the system.** An LLM is stateless per session. Without persistent context, every session starts cold — same questions, same rediscovery, no compounding. The knowledge base is what turns a capable but amnesiac assistant into something that builds on itself. Notes, decisions, indexes, and search are the core of a Claw — the LLM is the engine, but the KB is the continuity.

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
  code-reviews/   — automated code review output
  kb-design/      — notes about the KB system itself
  tasks/          — task tracker (backlog, active, completed, recurring)
  templates/      — writing scaffolds for all content types
  indexes.md      — directory of topic indexes
  WRITING.md      — detailed guide for creating and editing content
```

## Project Documentation

- [theory](../docs/theory.md) — theoretical framing: LLMs as probabilistic programs, hybrid VM, stabilise/soften, distribution shaping
- [architecture](../docs/architecture.md) — internal architecture: runtime, registry, call scopes, toolsets, UI pipeline
- [reference](../docs/reference.md) — API and usage reference for workers, tools, manifests, and configuration
- [scopes](../docs/scopes.md) — the three scopes (runtime, call, frame) governing resource lifecycle and state isolation
- [cli](../docs/cli.md) — CLI reference for `llm-do` command and manifest execution
- [ui](../docs/ui.md) — UI event pipeline: worker execution separated from rendering across Textual and headless modes
- [bootstrapping](../docs/bootstrapping.md) — (experimental) meta-worker that creates other workers from natural language descriptions

## Architecture Decisions

See [ADR index](./adr/index.md).

## Indexes

Two kinds:

- **Directory indexes** (`index.md` in each collection) — auto-generated flat listings. Rebuild with `uv run scripts/generate_notes_index.py <directory>`.
- **Area indexes** (e.g. `notes/approvals-index.md`) — curated navigation hubs with editorial context. Updated by `/connect` or manually.

## Search (qmd)

Collections: notes, adr, kb-design, sources, code-reviews, tasks-active, tasks-backlog, tasks-recurring, arscontexta, docs. Completed tasks intentionally excluded.

```bash
qmd query "search terms"     # hybrid search with reranking
qmd search "search terms"    # BM25 keyword search
qmd update && qmd embed      # re-index after changes
```

## Agent-initiated notes

Agent observations during work go to `notes/agent-learnings/` — low friction, no need to read WRITING.md. Periodically reviewed and promoted to the main KB or deleted.

## Writing

Read [WRITING.md](./WRITING.md) before creating or editing main KB content — templates, frontmatter, links, and quality checks.
