# Project Claw

A [Claw](./sources/simon-willison-karpathy-claws.md) — an AI-assisted system that accumulates context and evolves with use — scoped to the llm-do project. Also a live example of the crystallisation pattern it documents.

## Why this exists

**The memory is the system.** An LLM is stateless per session. Without persistent context, every session starts cold — same questions, same rediscovery, no compounding. The knowledge base is what turns a capable but amnesiac assistant into something that builds on itself. Notes, decisions, indexes, and search are the core of a Claw — the LLM is the engine, but the KB is the continuity.

**It showcases crystallisation.** A knowledge base for a project must evolve with that project — exactly the stabilise/soften cycle described in `docs/theory.md`. Notes start as freeform LLM-written explorations (soft), patterns get extracted into templates and indexes (stabilised), and when requirements shift, rigid structures get rethought (softened again). The KB itself follows the crystallisation gradient it documents.

## Current runtime: Claude Code

We prototype this system using Claude Code and Opus via subscription. Running Opus through the API would be too expensive for the volume of knowledge work involved. So for now, the KB operates on Claude Code's machinery: CLAUDE.md instructions, `.claude/skills/`, markdown files, and ripgrep queries.

The plan is to progressively port tooling to llm-do — search, connection-finding, health checks — as the patterns stabilise. This is itself crystallisation: what starts as LLM judgment guided by prose instructions becomes deterministic code as we learn what works. Eventually `project_claw/` moves to `examples/project_claw/` as a working example.

## Structure

This is the internal workspace — notes, decisions, explorations that accumulate during development. Each directory has an `index.md` listing its contents.

```
project_claw/
  notes/          — design notes, explorations, insights        [index](./notes/index.md)
  adr/            — architecture decision records                [index](./adr/index.md)
  sources/        — snapshots of external references             [index](./sources/index.md)
  kb-design/      — notes about the KB system itself             [index](./kb-design/index.md)
  skills/         — KB skills (connect, ingest) — symlinked from .claude/skills/
  scripts/        — KB helper scripts (index generation, topic sync, snapshots)
  code-reviews/   — automated code review output
  tasks/          — task tracker (backlog, active, completed, recurring)
  templates/      — writing scaffolds for all content types      [index](./templates/index.md)
  indexes.md      — directory of area indexes (curated, topical)
  WRITING.md      — detailed guide for creating and editing content
```

## Project documentation

The public-facing project documentation lives in [`docs/`](../docs/). That's the curated material for users and contributors — theory, architecture, reference. This workspace is where that documentation gets developed: design notes explore ideas, ADRs record decisions, and the results get distilled into `docs/`. We link to it from here because KB notes frequently reference and build on the public docs.

- [theory](../docs/theory.md) — LLMs as probabilistic programs, hybrid VM, stabilise/soften, distribution shaping
- [architecture](../docs/architecture.md) — runtime, registry, call scopes, toolsets, UI pipeline
- [reference](../docs/reference.md) — API and usage reference for agents, tools, manifests, configuration
- [scopes](../docs/scopes.md) — the three scopes (runtime, call, frame) governing resource lifecycle and state isolation
- [cli](../docs/cli.md) — CLI reference for `llm-do` command and manifest execution
- [ui](../docs/ui.md) — UI event pipeline: agent execution separated from rendering across Textual and headless modes
- [bootstrapping](../docs/bootstrapping.md) — (experimental) meta-agent that creates other agents from natural language descriptions

## Indexes

Two kinds:

- **Directory indexes** (`index.md` in each collection) — auto-generated flat listings. Rebuild with `uv run project_claw/scripts/generate_notes_index.py <directory>`.
- **Area indexes** (e.g. `notes/approvals-index.md`) — curated navigation hubs with editorial context. Updated by `/connect` or manually. See [indexes.md](./indexes.md) for the full list.

## Search (qmd)

Collections: notes, adr, kb-design, sources, skills, code-reviews, tasks-active, tasks-backlog, tasks-recurring, docs. Completed tasks intentionally excluded.

```bash
qmd query "search terms"     # hybrid search with reranking
qmd search "search terms"    # BM25 keyword search
qmd update && qmd embed      # re-index after changes
```

## Agent-initiated notes

Agent observations during work go to `notes/agent-learnings/` — low friction, no need to read WRITING.md. Periodically reviewed and promoted to the main KB or deleted.

## Writing

Read [WRITING.md](./WRITING.md) before creating or editing main KB content — templates, frontmatter, links, and quality checks.
