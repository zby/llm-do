---
description: Processing pipeline phases, session rhythm, queue management, and how skills chain together in llm-do development
type: manual
generated_from: "arscontexta-0.8.0"
---

# Workflows

This page documents how the knowledge system's skills chain together during llm-do development. It covers the processing pipeline, session rhythm, queue management, and common workflow patterns.

## The Processing Pipeline

Source material flows through four phases, each with a dedicated skill. The pipeline transforms raw content (design docs, PR discussions, research articles about LLM orchestration) into connected, verified notes in docs/notes/.

```
Source Material
    |
    v
[extract] -- Pull out insights relevant to llm-do
    |
    v
[connect] -- Find relationships to existing notes, update indexes
    |
    v
[revisit] -- Update older notes that predate the new one
    |
    v
[review]  -- Quality gate: description quality, schema, health checks
    |
    v
Done (note is graph-ready)
```

### Phase 1: Extract

**Skill:** `/arscontexta-extract`

**Input:** A source file (design document, research output, transcript)

**Output:** A set of note candidates with propositional titles, classified as CLOSED (standalone) or OPEN (needs investigation)

**What it extracts for llm-do:**

| Category | What to find | Example |
|----------|-------------|---------|
| Design decisions | Architecture choices, trade-offs | "agent-as-tool unifies the calling convention" |
| Technical insights | Implementation patterns, gotchas | "NullModel entries prevent uncontrolled tool use" |
| API design | Interface decisions, user experience | "toolset declaration by name decouples agents from implementations" |
| Integration patterns | How components interact, data flow | "syscall-style approval gates intercept at the tool boundary" |
| Open questions | Unresolved decisions | "should entries support direct tool access?" |

**Extraction principle:** For sources about llm-do (runtime architecture, agent specs, harness design, PydanticAI integration), comprehensive extraction is the default. Skip rate must stay below 10%.

**User approval required:** The skill presents candidates and waits for approval before creating files.

### Phase 2: Connect

**Skill:** `/arscontexta-connect`

**Input:** A newly created note in docs/notes/

**Output:** Wiki links added to the note, relevant indexes updated, synthesis opportunities flagged

**How it works:**
1. Reads the target note fully
2. Uses dual discovery: browse relevant indexes AND run semantic search
3. Evaluates each candidate with the articulation test
4. Adds inline wiki links for connections that pass
5. Updates index Core Ideas sections
6. Flags synthesis opportunities (A + B imply C, but C does not exist yet)

**Articulation test:** For every proposed connection, you must be able to complete: "[[A]] connects to [[B]] because [specific reason]." Generic "related" connections are rejected.

### Phase 3: Revisit

**Skill:** `/arscontexta-revisit`

**Input:** A note (typically one that predates newer related content)

**Output:** Updated note with new connections, sharpened claims, potential splits

**The backward pass:** Connect adds forward links (new note -> existing notes). Revisit does the reverse: it asks "if I wrote this older note today, with everything I now know about llm-do's runtime, what would be different?"

**Five actions available:**
1. Add connections to newer notes
2. Rewrite content to reflect deeper understanding
3. Sharpen vague claims into specific propositions
4. Split notes that grew to cover multiple ideas
5. Challenge claims that new evidence contradicts

### Phase 4: Review

**Skill:** `/arscontexta-review`

**Input:** A note to verify

**Output:** PASS/WARN/FAIL report across three verification categories

**Three checks in order:**
1. **Recite** -- cold-read prediction test. Read only title + description, predict content, then read full note and score accuracy. Tests whether agents can find this note via description alone.
2. **Validate** -- schema compliance against templates/note.md. Required fields (description, topics), enum values (status: current|outdated|speculative), constraints.
3. **Review** -- health checks. YAML integrity, description quality, index connection, wiki link density (>= 2 outgoing), link resolution.

**Passing threshold:** Prediction score 3+ out of 5. Any FAIL-level issue blocks completion.

---

## Session Rhythm

### Orient (start of every session)

```
1. Read self/identity.md     -- who you are in this project
2. Read self/methodology.md  -- how you process knowledge
3. Read self/goals.md        -- current active threads
4. Check ops/reminders.md    -- time-bound commitments
5. Run /arscontexta-next     -- recommended next action
```

Orientation takes 30 seconds of file reads. It provides continuity across sessions. Without it, you start cold and risk duplicating work or missing active threads.

### Work (main session)

The work phase is where llm-do development happens. Knowledge work serves the code:

**During development work:**
- When you make a design decision about the runtime, agent specs, or harness -- capture it as a note or ADR
- When you discover something unexpected about PydanticAI integration -- write it down
- When a PR discussion surfaces a trade-off -- extract the insight

**During knowledge work:**
- Process items from inbox/ through the pipeline
- Connect recently created notes
- Revisit older notes that reference outdated architecture
- Run /arscontexta-rethink if observations have accumulated

**Key principle:** The library comes first. Knowledge work serves the code, not the other way around. If you are spending more time on methodology than on design notes, recalibrate.

### Persist (end of every session)

```
1. Write new insights as notes in docs/notes/
2. Update relevant indexes
3. Update self/goals.md with current state
4. Capture methodology learnings via /arscontexta-remember
```

Session capture hooks save the transcript to ops/sessions/ automatically.

---

## Queue Management

### Queue Structure

The processing queue lives at `ops/queue/queue.json`. Each entry tracks one note through the pipeline:

```json
{
  "id": "claim-010",
  "type": "claim",
  "status": "pending",
  "target": "agent-as-tool makes callers agnostic to implementation",
  "classification": "closed",
  "batch": "architecture-review",
  "file": "architecture-review-010.md",
  "created": "2026-02-16T00:00:00Z",
  "current_phase": "connect",
  "completed_phases": ["create"]
}
```

**One entry per note, not one per phase.** Phase progression is tracked via `current_phase` and `completed_phases`.

### Phase Advancement

When a phase completes, the queue entry advances:

| current_phase | After completion, becomes |
|--------------|--------------------------|
| create | connect |
| connect | revisit |
| revisit | review |
| review | (status -> done) |

### Task Types

| Type | Description | Starting phase |
|------|-------------|---------------|
| `claim` | New note extracted from source | create |
| `enrichment` | Content to add to an existing note | enrich |
| `maintenance` | Condition-based maintenance work | varies |

### Queue Operations

- **View queue:** `/arscontexta-tasks`
- **Process N tasks:** `/arscontexta-ralph N`
- **Process specific batch:** `/arscontexta-ralph N --batch architecture-review`
- **Process specific phase:** `/arscontexta-ralph N --type connect`
- **Dry run:** `/arscontexta-ralph --dry-run`

---

## Pipeline Chaining Modes

Configured in ops/config.yaml under `processing.chaining`:

| Mode | Behavior |
|------|----------|
| **manual** | Each skill outputs "Next: /arscontexta-connect [note]" -- you decide when to proceed |
| **suggested** (default) | Outputs next step AND updates the queue -- you decide when to run it |
| **automatic** | Queue entries advance and the next phase runs immediately via orchestration |

---

## Common Workflow Patterns

### Pattern: Process a PR Discussion

A PR discussion about llm-do's approval gate design contains insights worth capturing.

1. Copy the discussion to `inbox/approval-gate-discussion.md`
2. `/arscontexta-seed inbox/approval-gate-discussion.md`
3. `/arscontexta-extract --handoff` (extracts claims, creates task files)
4. `/arscontexta-ralph 10` (processes all claims through connect -> revisit -> review)

### Pattern: Research and Integrate

You need to understand how other LLM frameworks handle tool authorization, to inform llm-do's syscall-style approval gates.

1. `/arscontexta-learn "LLM framework tool authorization patterns"` (researches topic, files to inbox/)
2. `/arscontexta-pipeline inbox/[research-output].md` (full pipeline)

### Pattern: Maintenance Pass

The vault has grown and needs attention.

1. `/arscontexta-next` (see what maintenance is recommended)
2. `/arscontexta-graph health` (identify orphans, dangling links, oversized indexes)
3. `/arscontexta-revisit --sparse` (connect the sparsest notes)
4. `/arscontexta-validate all` (batch schema check)
5. `/arscontexta-rethink` (if 10+ observations have accumulated)

### Pattern: Direct Capture During Development

While working on llm-do's entry point resolution, you realize that function entries running under NullModel is a deliberate safety constraint.

1. Write the note directly to `docs/notes/function entries use NullModel to prevent uncontrolled tool access.md`
2. `/arscontexta-connect [[function entries use NullModel to prevent uncontrolled tool access]]`
3. `/arscontexta-review function entries use NullModel to prevent uncontrolled tool access`

Direct writes to docs/notes/ are acceptable for insights that emerge during development. Run /arscontexta-connect afterward to integrate them into the graph.

---

## Condition-Based Maintenance

The system monitors conditions and surfaces maintenance work as queue entries when thresholds are crossed:

| Condition | Threshold | Recommended action |
|-----------|-----------|-------------------|
| Orphan notes | Any detected | `/arscontexta-connect` to find connections |
| Dangling wiki links | Any detected | Fix or remove broken links |
| Index size | > 40 notes | Consider splitting the index |
| Pending observations | >= 10 | `/arscontexta-rethink` |
| Pending tensions | >= 5 | `/arscontexta-rethink` |
| Inbox items | Older than 3 days | `/arscontexta-seed` + process |

These conditions are evaluated by `/arscontexta-next` during the orient phase. They materialize as maintenance tasks in the queue -- fix the underlying issue and the task goes away.

See [[configuration]] for how to adjust thresholds. See [[troubleshooting]] for when conditions persist unexpectedly.
