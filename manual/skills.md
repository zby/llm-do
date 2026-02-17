---
description: Complete command reference for all 26 skills -- 16 local processing skills and 10 plugin system skills
type: manual
generated_from: "arscontexta-0.8.0"
---

# Skills Reference

The llm-do knowledge system provides 26 skills divided into two categories:

- **16 local skills** -- Installed in `skills/` and `.claude/skills/`. Invoked as `/arscontexta-[name]`. These handle note processing, graph analysis, and system maintenance.
- **10 plugin skills** -- Provided by the arscontexta plugin. Invoked as `/arscontexta:[name]`. These handle system setup, architecture decisions, and cross-vault operations.

## Invocation Syntax

| Category | Syntax | Example |
|----------|--------|---------|
| Local skills | `/arscontexta-[name] [args]` | `/arscontexta-extract inbox/research.md` |
| Plugin skills | `/arscontexta:[name] [args]` | `/arscontexta:health --full` |

---

## Local Skills (16)

### Processing Pipeline Skills

These skills form the core pipeline that source material flows through. Each phase operates on notes in docs/notes/ and advances the queue entry in ops/queue/queue.json.

#### /arscontexta-extract

**Purpose:** Extract structured knowledge from source material into note candidates.

**Triggers:** `/extract`, `/extract [file]`, "extract insights", "process this"

**Arguments:**
- `[file path]` -- source file to extract from
- `--handoff` -- output RALPH HANDOFF block for orchestrated execution
- (empty) -- scan inbox/ for unprocessed items

**What it does:**
1. Reads the source file fully
2. Hunts for insights across extraction categories: design decisions, technical insights, API design, integration patterns, open questions
3. Checks each candidate against existing notes for duplicates via semantic search
4. Classifies candidates as CLOSED (standalone) or OPEN (needs investigation)
5. Presents findings for user approval before creating files

**Quality gates:** Comprehensive extraction is the default. For domain-relevant sources (about llm-do's runtime, agent specs, toolsets, etc.), skip rate must be below 10%. Zero extraction from a domain-relevant source is treated as a bug.

**Pipeline chaining:** After extraction, suggests `/arscontexta-connect` for each created note.

---

#### /arscontexta-connect

**Purpose:** Find connections between a note and the rest of the knowledge graph. The forward-connection phase.

**Triggers:** `/connect`, `/connect [note]`, "find connections", "update indexes"

**Arguments:**
- `[[note name]]` or note name -- find connections for a specific note
- `recent` or `new` -- connect all notes created today
- `--handoff` -- output RALPH HANDOFF block

**What it does:**
1. Reads the target note to understand its claim and reasoning
2. Uses dual discovery: index exploration AND semantic search in parallel
3. Evaluates each candidate connection with the articulation test
4. Adds inline wiki links where connections pass
5. Updates relevant indexes with the note
6. Detects synthesis opportunities (two notes that together imply a higher-order claim)

**Quality gates:** Every connection must pass the articulation test: "[[A]] connects to [[B]] because [specific reason]." Connections labeled merely "related" are rejected.

**Pipeline chaining:** After connecting, suggests `/arscontexta-revisit`.

---

#### /arscontexta-revisit

**Purpose:** Update older notes with new context. The backward pass that /arscontexta-connect does not do.

**Triggers:** `/revisit`, `/revisit [note]`, "update old notes", "backward connections"

**Arguments:**
- `[[note name]]` -- revisit a specific note
- `--sparse` -- process notes with fewest connections
- `--since Nd` -- revisit notes not updated in N days
- `--handoff` -- output RALPH HANDOFF block

**What it does:**
1. Reads the target note and asks: "If I wrote this today, what would be different?"
2. Searches for newer related notes via dual discovery
3. Evaluates the claim: does it still hold? Need sharpening? Splitting?
4. Applies changes: add connections, rewrite content, sharpen claims, split if needed
5. Updates indexes if topic membership changed

**Five actions:** Add connections, rewrite content, sharpen the claim, split the note, challenge the claim.

**Pipeline chaining:** After revisiting, suggests `/arscontexta-review`.

---

#### /arscontexta-review

**Purpose:** Combined quality gate -- description quality (cold-read prediction), schema compliance, and health checks.

**Triggers:** `/review`, `/review [note]`, "verify note quality", "check note health"

**Arguments:**
- `[note name]` -- verify a specific note
- `all` or `recent` -- verify recently created/modified notes
- `--handoff` -- output RALPH HANDOFF block

**What it does (in order):**
1. **Recite** -- reads only title + description, predicts content, then reads full note and scores prediction accuracy (1-5). Tests whether the description enables retrieval.
2. **Validate** -- checks all required fields from the template schema, verifies enum values, confirms constraints.
3. **Review** -- YAML integrity, description quality, index connection, wiki link density (>= 2 outgoing), link resolution.

**Scoring:** Prediction score 3+ passes. Any FAIL-level issue blocks completion. WARN items are informational.

**Pipeline position:** Final phase. After review passes, the pipeline is complete for that note.

---

### Orchestration Skills

#### /arscontexta-seed

**Purpose:** Add a source file to the processing queue.

**Triggers:** `/seed`, `/seed [file]`, "queue this for processing"

**Arguments:** `[file path]` -- source file to seed (checks inbox/ if not found at given path)

**What it does:**
1. Validates the source file exists
2. Checks for duplicate processing
3. Creates an archive folder structure
4. Moves the source from inbox/ to the archive
5. Creates an extract task in ops/queue/queue.json

---

#### /arscontexta-ralph

**Purpose:** Autonomous queue processor. Spawns isolated subagents for each task phase to prevent context contamination.

**Triggers:** `/ralph`, `/ralph N`, "process queue", "run pipeline tasks"

**Arguments:**
- `N` (required unless --dry-run) -- number of tasks to process
- `--parallel` -- concurrent claim workers (max 5)
- `--batch [id]` -- process only tasks from a specific batch
- `--type [type]` -- process only tasks at a specific phase
- `--dry-run` -- show what would execute without running

**What it does:** Reads the queue, picks N tasks, spawns a fresh-context subagent for each task's current phase, evaluates the handoff output, advances the queue, repeats.

**Constraint:** Every task MUST be spawned as a subagent via the Task tool. The lead session never executes task work inline -- this is a hard architectural constraint, not a performance suggestion.

---

#### /arscontexta-pipeline

**Purpose:** End-to-end source processing in one command. Chains seed, extract, and all claim phases.

**Triggers:** `/pipeline`, `/pipeline [file]`, "process this end to end", "full pipeline"

**Arguments:** `[file path]` -- source file to process

**What it does:** Runs `/arscontexta-seed`, then `/arscontexta-extract --handoff`, then `/arscontexta-ralph` for all resulting claim tasks through connect, revisit, and review phases.

---

#### /arscontexta-tasks

**Purpose:** View and manage the processing queue.

**Triggers:** `/tasks`, "show queue", "what's pending"

**Arguments:** Subcommands for listing, filtering, and managing queue entries.

---

### Analysis Skills

#### /arscontexta-graph

**Purpose:** Interactive knowledge graph analysis. Routes natural language questions to graph operations.

**Triggers:** `/graph`, `/graph health`, `/graph triangles`, "find synthesis opportunities"

**Operations:**
- `health` -- orphan detection, dangling links, link density metrics
- `triangles` -- find synthesis opportunities (A connects to B, B connects to C, but A does not connect to C)
- `bridges` -- notes that connect otherwise-separate clusters
- `clusters` -- identify topic clusters in the graph
- `hubs` -- notes with the most incoming links
- `siblings` -- notes that share the same connections
- `forward [note]` -- outgoing connections from a note
- `backward [note]` -- incoming connections to a note
- `query [pattern]` -- custom graph queries

---

#### /arscontexta-stats

**Purpose:** Vault metrics and knowledge graph health snapshot.

**Triggers:** `/stats`, "vault stats", "show metrics", "how big is my vault"

**Arguments:** `--share` for compact shareable output

**Metrics reported:** Note count, link count, link density, index coverage, orphan count, queue status, processing progress, growth rate.

---

#### /arscontexta-next

**Purpose:** Recommend the single most valuable next action.

**Triggers:** `/next`, "what should I do", "what's next"

**What it evaluates:**
1. Task queue -- pending pipeline work
2. Inbox pressure -- items older than 3 days
3. Maintenance conditions -- orphan notes, dangling links, oversized indexes
4. Observation/tension thresholds -- 10+ observations or 5+ tensions trigger /arscontexta-rethink
5. Goals -- active threads from self/goals.md

**Constraint:** /arscontexta-next recommends, it does not execute. It presents one recommendation with rationale and lets the user decide.

---

### Quality Skills

#### /arscontexta-validate

**Purpose:** Schema validation for notes against templates.

**Triggers:** `/validate`, `/validate [note]`, "check schema", "validate all"

**Arguments:**
- `[note name]` -- validate a specific note
- `all` -- validate all notes in docs/notes/

**Checks:** Required fields, enum values, description quality, YAML validity, link health. Non-blocking -- warns but does not prevent capture.

**Difference from /arscontexta-review:** Validate checks schema compliance only. Review adds the cold-read prediction test and comprehensive health checks. Use validate for quick checks, review for the full quality gate.

---

### Research Skills

#### /arscontexta-learn

**Purpose:** Research a topic and file results with full provenance for pipeline processing.

**Triggers:** `/learn`, `/learn [topic]`, "research this", "find out about"

**Arguments:**
- `[topic]` -- what to research
- `--deep` / `--moderate` / `--light` -- force research depth

**What it does:**
1. Researches the topic using available tools (web search, Exa deep researcher)
2. Files results to inbox/ with provenance metadata (source_type, research_prompt, generated timestamp)
3. Chains to the processing pipeline based on config chaining mode
4. Updates self/goals.md with new research directions discovered

**llm-do example:** `/arscontexta-learn "PydanticAI agent dependency injection patterns"` researches how PydanticAI handles DI, files results for extraction, and surfaces insights relevant to llm-do's toolset resolution.

---

### System Evolution Skills

#### /arscontexta-remember

**Purpose:** Capture operational friction as methodology notes.

**Triggers:** `/remember`, `/remember [description]`

**Three modes:**
- **Explicit** -- `/arscontexta-remember "extraction skips implementation ideas"` -- directly describe the friction
- **Contextual** -- `/arscontexta-remember` (no args) -- review recent conversation for corrections and patterns
- **Session mining** -- `/arscontexta-remember --mine` -- scan ops/sessions/ for recurring patterns

See [[meta-skills]] for detailed usage.

---

#### /arscontexta-rethink

**Purpose:** Challenge system assumptions against accumulated evidence. Triage observations and tensions, detect patterns, generate improvement proposals.

**Triggers:** `/rethink`, "review observations", "challenge assumptions"

**Arguments:**
- (empty) -- full six-phase rethink on all pending observations and tensions
- `triage` -- Phase 1 only (triage and methodology updates)
- `patterns` -- Phases 3-5 only (analyze existing evidence)
- `drift` -- Phase 0 only (configuration drift check)

See [[meta-skills]] for detailed usage.

---

#### /arscontexta-refactor

**Purpose:** Plan and execute vault restructuring from config changes.

**Triggers:** `/refactor`, "restructure vault"

**Arguments:**
- (empty) -- detect all config changes and plan restructuring
- `[dimension]` -- focus on a specific dimension (granularity, organization, linking, etc.)
- `--dry-run` -- show plan without asking for approval

**What it does:** Compares ops/config.yaml against ops/derivation.md to find dimension shifts, then generates a restructuring plan. Never executes without approval.

---

## Plugin Skills (10)

Plugin skills are provided by the arscontexta engine and handle system-level operations. They use the `/arscontexta:[name]` invocation pattern.

### /arscontexta:setup

**Purpose:** Initialize the knowledge system for a new project. Creates self/, ops/, templates/, manual/, and configures all dimensions based on a conversation about the project.

**When to use:** Once, at project inception. Already completed for llm-do.

---

### /arscontexta:add-domain

**Purpose:** Add a new domain to a multi-domain knowledge system.

**When to use:** If llm-do's knowledge system needed to track a second project. Currently single-domain.

---

### /arscontexta:tutorial

**Purpose:** Interactive walkthrough of a specific capability.

**Arguments:** Topic to learn about (e.g., "extraction", "graph analysis", "pipeline")

**When to use:** When you want guided, hands-on learning rather than reading documentation.

---

### /arscontexta:architect

**Purpose:** Modify system structure, schema, or methodology with architectural reasoning.

**When to use:** When you need to change how the knowledge system works -- add schema fields, change note templates, restructure indexes.

---

### /arscontexta:health

**Purpose:** Systematic vault diagnostics. Broader than `/arscontexta-graph health` -- covers schema compliance, processing pipeline status, and system configuration.

**Arguments:** `--full` for comprehensive audit

---

### /arscontexta:reseed

**Purpose:** Regenerate skills and configuration from updated engine version or derivation changes.

**When to use:** After upgrading the arscontexta engine version or making derivation changes.

---

### /arscontexta:recommend

**Purpose:** Cross-vault feature recommendations based on usage patterns.

**When to use:** When exploring what capabilities to activate or adjust.

---

### /arscontexta:ask

**Purpose:** Query two knowledge layers -- local methodology (ops/methodology/) and bundled research -- to answer questions about knowledge system design.

**When to use:** When you want to understand WHY the system is configured a certain way, or research best practices for a knowledge management question.

See [[meta-skills]] for detailed usage.

---

### /arscontexta:help

**Purpose:** Show available commands and what they do. The entry point for discovering capabilities.

---

### /arscontexta:upgrade

**Purpose:** Upgrade the knowledge system to a newer arscontexta engine version.

**When to use:** When a new engine version is available with improved skills or configuration options.

---

## Skill Routing Quick Reference

| I want to... | Use this skill |
|--------------|---------------|
| Process a new source document | `/arscontexta-pipeline [file]` or `/arscontexta-seed` + `/arscontexta-extract` |
| Find connections for a note | `/arscontexta-connect [[note]]` |
| Update old notes with new context | `/arscontexta-revisit [[note]]` |
| Check note quality | `/arscontexta-review [note]` |
| Run batch queue processing | `/arscontexta-ralph N` |
| See what to work on | `/arscontexta-next` |
| Check vault health | `/arscontexta-graph health` or `/arscontexta:health` |
| Research a topic for llm-do | `/arscontexta-learn "topic"` |
| Record a process improvement | `/arscontexta-remember "description"` |
| Review accumulated friction | `/arscontexta-rethink` |
| Get vault metrics | `/arscontexta-stats` |
| Validate schema compliance | `/arscontexta-validate all` |
| Restructure after config change | `/arscontexta-refactor` |
| Get help | `/arscontexta:help` |
| Modify system architecture | `/arscontexta:architect` |

See [[workflows]] for how these skills chain together in practice.
