---
description: Guide to arscontexta/ops/config.yaml -- system dimensions, processing depth, feature flags, and tuning for llm-do development
type: manual
generated_from: "arscontexta-0.8.0"
---

# Configuration

The knowledge system's behavior is controlled by `arscontexta/ops/config.yaml`. This file is the live configuration that all skills read at runtime. Changes take effect immediately on the next skill invocation.

For the reasoning behind each configuration choice, see `arscontexta/ops/derivation.md`. For the machine-readable manifest used by skills at runtime, see `arscontexta/ops/derivation-manifest.md`.

## Current Configuration (llm-do)

```yaml
dimensions:
  granularity: moderate
  organization: hierarchical
  linking: explicit
  processing: moderate
  navigation: 3-tier
  maintenance: condition-based
  schema: moderate
  automation: full

features:
  semantic-search: false
  processing-pipeline: true
  sleep-processing: false
  voice-capture: false

processing:
  depth: standard
  chaining: suggested
  extraction:
    selectivity: moderate
    categories:
      - design-decisions
      - technical-insights
      - api-design
      - integration-patterns
      - open-questions
  verification:
    description_test: true
    schema_check: true
    link_check: true
  reweave:
    scope: related
    frequency: after_create

domain:
  name: llm-do
  type: library-development
  public_docs_path: docs/
  internal_workspace:
    - docs/notes/
    - docs/adr/
    - tasks/
```

---

## Dimensions

Dimensions are the system's structural parameters. They were set during `/arscontexta:setup` based on the llm-do project's characteristics. To change a dimension, edit arscontexta/ops/config.yaml and run `/arscontexta-refactor` to plan the restructuring.

### granularity: moderate

Notes are per-entry (one insight per note, but not atomically decomposed claims). This matches llm-do's existing convention of per-topic design notes in docs/notes/.

| Value | Behavior |
|-------|----------|
| atomic | One claim per note, heavily decomposed |
| **moderate** | Per-entry notes, each covering one insight or decision |
| coarse | Longer documents covering broader topics |

**Why moderate for llm-do:** The existing docs/notes/ files are per-topic. ADRs are per-decision. Tasks are per-work-item. Moderate granularity preserves these conventions.

### organization: hierarchical

Notes use the existing docs/notes/ subcategory structure (docs/notes/agent-learnings/, etc.) and are organized by indexes.

| Value | Behavior |
|-------|----------|
| flat | All notes in one directory |
| **hierarchical** | Subdirectories for categories |
| tagged | Flat directory with tag-based organization |

### linking: explicit

Internal workspace documents connect via wiki links. Every `[[link]]` is a deliberate edge in the knowledge graph.

| Value | Behavior |
|-------|----------|
| none | No internal linking |
| **explicit** | Wiki links between notes, ADRs, and tasks |
| auto | Automatic link suggestion |

### processing: moderate

Balanced between tracking and doing. Notes go through the four-phase pipeline but without excessive ceremony.

| Value | Behavior |
|-------|----------|
| minimal | Capture only, no structured processing |
| **moderate** | Four-phase pipeline with quality gates |
| heavy | Deep processing with multiple review rounds |

### navigation: 3-tier

Hub (this manual) -> area indexes -> individual notes. The three tiers provide navigation without excessive hierarchy.

### maintenance: condition-based

Maintenance triggers based on conditions (orphan count, dangling links, observation accumulation) rather than on a fixed schedule. Conditions are evaluated by `/arscontexta-next`.

### schema: moderate

Notes in docs/notes/ have YAML frontmatter with required fields (description, areas). Public docs in docs/*.md are untouched.

### automation: full

All skills, hooks, and maintenance mechanisms are available. Claude Code platform supports subagent spawning for `/arscontexta-ralph`.

---

## Processing Configuration

### processing.depth

Controls how thoroughly each pipeline phase operates.

| Value | Extract | Connect | Revisit | Review |
|-------|---------|---------|---------|--------|
| **deep** | Fresh context per chunk, maximum quality gates | Full dual discovery, multiple passes, synthesis detection | Full reconsideration, extensive search | Cold-read + schema + health + orphan risk + staleness + bundling |
| **standard** | Sequential chunk processing, balanced attention | Dual discovery, top 5-10 candidates | Balanced review, same-index + semantic neighbors | Cold-read + schema + health |
| **quick** | Larger chunks, fewer passes | Single pass, obvious connections only | Minimal backward pass, no rewrites | Schema + link verification only |

**Recommendation for llm-do:** Use `standard` for regular work. Switch to `deep` when processing architecturally significant sources (like docs/theory.md or docs/architecture.md changes). Use `quick` for high-volume catch-up.

### processing.chaining

Controls how pipeline phases hand off to each other.

| Value | Behavior |
|-------|----------|
| manual | Output "Next: /arscontexta-connect [note]" -- you decide |
| **suggested** | Output next step AND update queue -- you decide when to run |
| automatic | Next phase runs immediately via orchestration |

### processing.extraction.selectivity

Controls the gate for filtering off-topic content during extraction.

| Value | Behavior |
|-------|----------|
| strict | 4-criterion gate applies to ALL claims including domain-relevant |
| **moderate** | Gate applies only to off-topic content. Domain-relevant bypasses gate |
| permissive | Gate barely applies. Extract nearly everything |

**For llm-do:** Moderate is appropriate. Sources about the runtime, agent specs, and harness are domain-relevant and bypass the gate. General software engineering articles go through the selectivity filter.

### processing.extraction.categories

The extraction categories define what `/arscontexta-extract` hunts for. Currently configured for llm-do library development:

- **design-decisions** -- Architecture choices, trade-offs, rationale for technical decisions in the runtime, harness, or agent system
- **technical-insights** -- Learnings about implementation patterns, PydanticAI gotchas, Python async patterns
- **api-design** -- Interface decisions, `.agent` file design, toolset APIs, project manifest conventions
- **integration-patterns** -- How components interact: agents calling agents, entries dispatching, approval gate flow
- **open-questions** -- Unresolved decisions: entry capabilities, scope boundaries, model configuration

To add a category, append it to this list and update `arscontexta/ops/derivation-manifest.md` with the new category's `what_to_find` and `output_type`.

### processing.verification

Controls which checks `/arscontexta-review` runs:

| Check | What it does | Default |
|-------|-------------|---------|
| description_test | Cold-read prediction test | true |
| schema_check | Validate against template schema | true |
| link_check | Verify all wiki links resolve | true |

Disabling a check skips it during review. This is useful for quick passes but not recommended for regular use.

### processing.reweave

Controls `/arscontexta-revisit` behavior:

| Setting | Values | Default |
|---------|--------|---------|
| scope | related, broad, full | related |
| frequency | after_create, periodic, manual | after_create |

- **scope: related** -- Search notes in the same index and semantic neighbors
- **scope: broad** -- Search across all indexes and semantic space
- **scope: full** -- Complete review including potential splits, rewrites, and claim challenges
- **frequency: after_create** -- Revisit runs after every new note creation (as part of the pipeline)

---

## Feature Flags

| Feature | Status | Description |
|---------|--------|-------------|
| semantic-search | false | Vector search via qmd. Enable when qmd is installed and collections are indexed. |
| processing-pipeline | true | The four-phase pipeline. Core feature, should stay enabled. |
| sleep-processing | false | Background processing during idle time. Not implemented for Claude Code. |
| voice-capture | false | Voice-to-text capture to inbox. Not applicable. |

### Enabling semantic search

If qmd (or another vector search tool) is available:

1. Set `features.semantic-search: true` in arscontexta/ops/config.yaml
2. Index your notes collection: `qmd update && qmd embed`
3. Skills will automatically use vector search for duplicate detection and connection finding

When semantic search is disabled, skills fall back to keyword search (ripgrep) and index browsing. This works but misses same-concept-different-words connections.

---

## Domain Configuration

```yaml
domain:
  name: llm-do
  type: library-development
  public_docs_path: docs/
  internal_workspace:
    - docs/notes/
    - docs/adr/
    - tasks/
```

**public_docs_path** -- Files under this path are NOT part of the knowledge system. No schema enforcement, no wiki links, no frontmatter changes. For llm-do, this means docs/architecture.md, docs/cli.md, docs/reference.md, docs/theory.md, docs/scopes.md, docs/ui.md, and docs/bootstrapping.md are all off-limits.

**internal_workspace** -- Directories where the knowledge system operates. Schema enforcement, wiki links, and indexes apply here.

---

## Research Configuration

```yaml
research:
  primary: web-search
  fallback: web-search
  last_resort: web-search
  default_depth: moderate
```

Controls the tool cascade for `/arscontexta-learn`:
1. Try `primary` tool first
2. If unavailable, try `fallback`
3. If both fail, try `last_resort`

Currently all set to web-search. If Exa MCP tools are available, set `primary: exa-deep-researcher` for higher-quality research output.

---

## Provenance Configuration

```yaml
provenance: minimal
```

Controls how much source attribution metadata is preserved:

| Value | Behavior |
|-------|----------|
| **minimal** | Source file linked in footer. No line numbers or full provenance chain. |
| standard | Source file, line numbers, research prompt preserved |
| full | Complete provenance chain including research tool, timestamp, and query |

---

## Changing Configuration

1. Edit `arscontexta/ops/config.yaml` directly
2. For dimension changes (granularity, organization, etc.): run `/arscontexta-refactor` to plan restructuring
3. For processing changes (depth, chaining, selectivity): takes effect immediately on next skill invocation
4. For feature flags: takes effect immediately

**Important:** Dimension changes may require restructuring notes, indexes, or templates. Always run `/arscontexta-refactor` after changing a dimension -- it compares the new config against arscontexta/ops/derivation.md and generates a migration plan.

See [[workflows]] for how configuration affects pipeline behavior. See [[meta-skills]] for how /arscontexta:architect handles structural changes.
