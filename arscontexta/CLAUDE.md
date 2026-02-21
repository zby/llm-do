# Arscontexta — Processing Pipeline & Operations

This file contains arscontexta-specific configuration: session rhythm, operational space, processing pipeline, maintenance, skills, and self-evolution. For project-wide knowledge system guidance (links, indexes, schema, discovery-first design), see the root `CLAUDE.md`.

## Session Rhythm

Every session follows: **Orient → Work → Persist**

### Orient

Read identity and goals at session start. Check condition-based triggers for maintenance items.

- `arscontexta/self/identity.md`, `arscontexta/self/methodology.md`, `arscontexta/self/goals.md` — who you are, what you're working on
- `arscontexta/ops/reminders.md` — time-bound commitments (surface overdue items)
- Workboard reconciliation — surfaces condition-based maintenance triggers automatically

### Work

Do the actual task. Surface connections as you go. If you discover something worth keeping, write it down immediately — it won't exist next session otherwise.

### Persist

Before session ends:
- Write any new insights as notes in docs/notes/
- Update relevant indexes
- Update arscontexta/self/goals.md with current state
- Capture anything learned about methodology
- Session capture: stop hooks save transcript to arscontexta/ops/sessions/

## Your Mind Space (arscontexta/self/)

This is YOUR persistent memory. Read it at EVERY session start.

```
arscontexta/self/
├── identity.md      — who you are, your approach
├── methodology.md   — how you work, principles
├── goals.md         — current threads, what's active
└── memory/          — atomic insights you've captured
```

**identity.md** — Your role in this project, values, working style. Update as you learn.
**methodology.md** — How you process and connect knowledge. Evolves as you improve.
**goals.md** — What you're working on right now. Update at session end.
**memory/** — Atomic notes with prose-as-title. Your accumulated understanding.

## Where Arscontexta Content Goes

| Content Type | Destination | Examples |
|-------------|-------------|----------|
| Quick captures, raw ideas | arscontexta/inbox/ | URLs, rough thoughts, things to process later |
| Agent identity, methodology, preferences | arscontexta/self/ | Working patterns, goals, learned preferences |
| Time-bound commitments | arscontexta/ops/reminders.md | Follow-ups, deadlines, things to revisit |
| Processing state, queue, config | arscontexta/ops/ | Queue state, session logs, observations |
| Friction signals, patterns noticed | arscontexta/ops/observations/ | Search failures, methodology improvements |

When uncertain, ask: "Is this agent identity (arscontexta/self/) or temporal coordination (arscontexta/ops/)?"

## Operational Space (arscontexta/ops/)

```
arscontexta/ops/
├── derivation.md         — why this system was configured this way
├── derivation-manifest.md — machine-readable config for runtime skills
├── config.yaml           — live configuration (edit to adjust dimensions)
├── reminders.md          — time-bound commitments
├── tasks.md              — knowledge processing task overview
├── observations/         — friction signals, patterns noticed
├── tensions/             — contradictions between notes
├── methodology/          — vault self-knowledge
├── queue/                — processing queue (separate from tasks/)
└── sessions/             — session logs
```

## Infrastructure Routing

When users ask about system structure, schema, or methodology:

| Pattern | Route To | Fallback |
|---------|----------|----------|
| "How should I organize/structure..." | /arscontexta:architect | Apply methodology below |
| "Can I add/change the schema..." | /arscontexta:architect | Edit templates directly |
| "Research best practices for..." | /arscontexta:ask | Read bundled references |
| "What does my system know about..." | Check arscontexta/ops/methodology/ directly | /arscontexta:ask for research backing |
| "What should I work on..." | /arscontexta:next | Reconcile queue + recommend |
| "Help / what can I do..." | /arscontexta:help | Show available commands |
| "Walk me through..." | /arscontexta:tutorial | Interactive learning |
| "Research / learn about..." | /arscontexta:learn | Deep research with provenance |

## Processing Pipeline

**Depth over breadth. Quality over speed.**

Every piece of content follows: capture → extract → connect → review. Each phase has a distinct purpose.

### The Phases

**Phase 1: Capture** — Zero friction. Everything enters through `arscontexta/inbox/` or directly to `docs/notes/`. Speed of capture beats precision of filing.

**Phase 2: Extract** — Read source material through the project lens: "Does this serve understanding of llm-do?" Pull out design decisions, technical insights, API design observations, integration patterns, and open questions.

Quality bar for extracted notes:
- Title works as prose when linked
- Description adds information beyond the title
- Insight is specific enough to disagree with

**Phase 3: Connect** — After creating notes, find relationships to existing notes, ADRs, and tasks. Add links and update relevant indexes. Check what older notes should link to the new ones.

**Phase 4: Review** — Description quality test (cold-read the title + description — can you predict the content?), schema compliance, no broken links, index membership.

### Processing Depth

Configured in arscontexta/ops/config.yaml:
- **deep** — Full pipeline, fresh context per phase, maximum quality gates
- **standard** — Full pipeline, balanced attention (default)
- **quick** — Compressed pipeline, combine connect+review. For high volume catch-up.

### Pipeline Chaining

- **manual** — Skills output "Next: /[skill] [target]" — you decide
- **suggested** — Skills output next step AND add to task queue (default)
- **automatic** — Skills complete → next phase runs immediately

### Task Queue

Pipeline tasks are tracked in `arscontexta/ops/queue/queue.json`. Each note gets one queue entry progressing through phases. /next evaluates conditions and recommends the highest-priority action.

Maintenance work lives alongside pipeline work in the same queue. Conditions materialize as `type: "maintenance"` entries with priority based on consequence speed.

## Templates — Schema as Scaffolding

Templates live in `arscontexta/templates/` and define the structure of each note type:
- `arscontexta/templates/note.md` — for docs/notes/ design notes
- `arscontexta/templates/adr.md` — for docs/adr/ architecture decisions
- `arscontexta/templates/index.md` — for area indexes
- `arscontexta/templates/observation.md` — for arscontexta/ops/observations/

Each includes a `_schema` block defining required fields, optional fields, enums, and constraints. The `_schema` block is the single source of truth for validation.

Notes are validated against these templates. Validation catches drift without blocking capture. Missing descriptions are FAIL; missing optional fields are WARN.

## Maintenance — Keeping the Graph Healthy

### Condition-Based Triggers

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Orphan notes | Any detected | Surface for connection-finding |
| Dangling links | Any detected | Surface for resolution |
| Index size | >40 notes | Suggest split |
| Pending observations | >=10 | Suggest /rethink |
| Pending tensions | >=5 | Suggest /rethink |
| Inbox pressure | Items older than 3 days | Suggest processing |

These are evaluated by /next via queue reconciliation. Conditions materialize as maintenance tasks — fix the underlying issue and the task goes away.

### Reweaving — The Backward Pass

New notes create connections going forward. But older notes don't know about newer ones. Revisiting is the practice of asking: "If I wrote this today, what would be different?"

Reweaving can:
- Add connections to newer notes
- Sharpen a claim with better understanding
- Split a note that contains multiple ideas
- Challenge a claim that new evidence contradicts

## Self-Evolution — How This System Grows

Complexity arrives at pain points, not before. You don't add features because they seem useful — you add them because you've hit friction.

### The Pattern

1. Work with your current setup
2. Notice friction — something repeatedly takes too long or gets forgotten
3. Use /remember to capture the friction signal
4. Identify which module addresses that friction
5. Activate and adapt it
6. Monitor — did the friction decrease?

### Your System's Self-Knowledge (arscontexta/ops/methodology/)

Your vault knows why it was built the way it was. `arscontexta/ops/methodology/` contains linked notes explaining configuration rationale, learned behavioral patterns, and operational evolution.

| Content | Created By | Purpose |
|---------|-----------|---------|
| Derivation rationale | /setup | Why each dimension was configured this way |
| Behavioral patterns | /remember | Learned corrections and guidance |
| Configuration state | /rethink, /architect | Active features, adjustments |

Query your methodology directly:
```bash
ls arscontexta/ops/methodology/*.md
rg '^category:' arscontexta/ops/methodology/
rg '^status: active' arscontexta/ops/methodology/
```

The /ask command consults two knowledge layers:
- **Local methodology** (arscontexta/ops/methodology/) — "How does MY system work?"
- **Research graph** (bundled methodology notes) — "Why is this a good idea?"

### Operational Learning Loop

**Observations** (arscontexta/ops/observations/) — friction, surprises, process gaps captured during work.
**Tensions** (arscontexta/ops/tensions/) — contradictions between notes or between methodology and practice.

Thresholds: 10+ pending observations or 5+ pending tensions → run /rethink to triage.

## Graph Analysis — Queryable Database

Your linked workspace is a graph database: markdown files are nodes, links are edges, YAML frontmatter is the property store, ripgrep is the query engine.

### Three Query Levels

**Level 1: Field-Level** — Query YAML fields: `rg '^description:.*oauth' docs/notes/`
**Level 2: Node-Level** — Query a note's connections: backlinks, outgoing links
**Level 3: Graph-Level** — Structural analysis: clusters, bridges, synthesis opportunities

### Key Operations

| Situation | What to Do |
|-----------|------------|
| Just created new notes | Find connections you missed (triangle detection) |
| Graph feels disconnected | Find clusters and bridging opportunities |
| Health check | Orphan detection + dangling links + link density |
| Preparing synthesis | Map the neighborhood of key notes |

## Pipeline Compliance

New insights should route through the pipeline: `arscontexta/inbox/` → `/extract` → `docs/notes/`. Direct writes to docs/notes/ are acceptable for design explorations that emerge during development work — just make sure to run /connect afterward so the note gets linked into the graph.

Full automation is active from day one. All processing skills, all quality gates, all maintenance mechanisms are available immediately.

## Self-Improvement

When friction occurs (search fails, content placed wrong, user corrects you):
1. Use /remember to capture it as an observation in arscontexta/ops/observations/
2. Continue your current work — don't derail
3. If the same friction occurs 3+ times, propose updating this context file
4. If user explicitly says "remember this" or "always do X", update this context file immediately

## Self-Extension

You can extend this system yourself:

### Building New Skills
Create `.claude/skills/skill-name/SKILL.md` with YAML frontmatter and instructions.

### Building Hooks
Create `.claude/hooks/` scripts that trigger on events (SessionStart, PostToolUse, Stop).

### Extending Schema
Add domain-specific YAML fields to templates. The base fields are universal; add fields that make YOUR notes queryable.

### Growing Indexes
When an index exceeds ~35 notes, split it. Create sub-indexes that link back to the parent.

## System Evolution

This system was seeded for library development. It will evolve through use.

### Expect These Changes
- **Schema expansion** — Fields worth tracking that aren't in the template yet
- **Index splits** — When a topic area exceeds ~35 notes
- **New note types** — Beyond design notes and ADRs, you may need tension notes, methodology notes, or synthesis notes

### Signs of Friction (act on these)
- Notes accumulating without connections → increase connection-finding frequency
- Can't find what you know exists → add more index structure
- Schema fields nobody queries → remove them
- Processing feels perfunctory → simplify the cycle

### Derivation Rationale

This system was derived for the llm-do project with these key choices:
- **Moderate granularity** — per-entry notes (not atomic claims) matching existing conventions
- **Hierarchical organization** — preserving existing docs/notes/ subcategories
- **Explicit linking** — standard markdown links between internal workspace documents
- **Moderate processing** — balancing tracking with doing
- **Full automation** — leveraging Claude Code hooks and skills
- **Public/internal boundary** — docs/*.md untouched; docs/notes/, docs/adr/, tasks/ enhanced

See `arscontexta/ops/derivation.md` for the complete derivation with conversation signals and confidence levels.

## Guardrails

- Derivation rationale (arscontexta/ops/derivation.md) is always readable
- No hidden processing — every automated action is logged and inspectable

## Available Skills

### Local Processing Skills (16)

Invoke with `/[name]`:

- /extract — Extract insights from source material
- /connect — Find connections between notes
- /review — Check note quality and schema compliance
- /revisit — Update older notes with new context
- /validate — Batch schema validation
- /seed — Queue source for processing
- /ralph — Autonomous processing loop
- /pipeline — Run full processing sequence
- /tasks — View and manage processing queue
- /stats — Vault metrics and progress
- /graph — Graph analysis and queries
- /next — Next recommended action
- /learn — Research a topic and grow the graph
- /remember — Capture operational friction
- /rethink — Review accumulated observations
- /refactor — Restructure notes and indexes

### Plugin Commands (10)

Invoke with `/arscontexta:[name]`:

- /arscontexta:setup — Scaffold a knowledge system
- /arscontexta:health — Vault health diagnostics
- /arscontexta:ask — Query methodology knowledge base
- /arscontexta:architect — Research-backed evolution advice
- /arscontexta:help — Contextual guidance and command discovery
- /arscontexta:tutorial — Interactive walkthrough
- /arscontexta:add-domain — Add a new knowledge domain
- /arscontexta:recommend — Architecture advice
- /arscontexta:upgrade — Apply methodology updates
- /arscontexta:reseed — Re-derive from first principles
