---
description: First session guide for the llm-do knowledge system -- orientation, first note, first pipeline run
type: manual
generated_from: "arscontexta-0.8.0"
---

# Getting Started

This guide walks through your first session with the llm-do knowledge system. By the end, you will have oriented yourself, created a note, and run it through the processing pipeline.

## Prerequisites

The knowledge system runs inside Claude Code on the llm-do project. It requires:

- Claude Code with the arscontexta skills installed in `.claude/skills/` and `skills/`
- The ops/ directory with config.yaml and derivation-manifest.md
- The self/ directory with identity.md, methodology.md, goals.md
- The templates/ directory with note.md, adr.md, index.md, observation.md

All of these are created during `/arscontexta:setup`. If they do not exist, run setup first.

## Session Rhythm: Orient, Work, Persist

Every session follows three phases. This is not optional -- it is how continuity works across sessions.

### Orient

Read your persistent memory and current state:

1. **Read self/** -- `self/identity.md`, `self/methodology.md`, `self/goals.md`. These tell you who you are, how you work, and what you are currently working on.
2. **Check ops/reminders.md** -- Surface any overdue time-bound commitments.
3. **Run `/arscontexta-next`** -- Get a recommended action based on queue state, inbox pressure, and goals.

The orientation phase takes 30 seconds of reading. It prevents the common failure of starting work without context from prior sessions.

### Work

Do the actual task. This is where most of the session is spent. As you work on llm-do -- designing the runtime, refining agent specs, building toolsets -- capture insights that would be lost between sessions.

### Persist

Before the session ends:

1. Write new insights as notes in docs/notes/
2. Update relevant indexes
3. Update self/goals.md with current state
4. Capture methodology learnings

Session hooks handle some of this automatically, but goals.md updates require your judgment.

## Your First Note

Suppose you discover during development that llm-do's agent-as-tool pattern means calling agents and calling tools are indistinguishable to the calling LLM. This is worth capturing.

### Step 1: Write the note

Create a file at `docs/notes/agent-as-tool makes callers agnostic to implementation.md`:

```markdown
---
description: When agents appear as tools, the calling LLM cannot distinguish neural from symbolic execution, enabling free movement between the two
areas: []
status: current
---

# agent-as-tool makes callers agnostic to implementation

The agent-as-tool pattern in llm-do wraps agents via AgentToolset so they appear as callable tools to the calling LLM. The caller does not know -- and cannot know -- whether a tool is backed by Python code or another agent.

This agnosticism is what makes the boundary between neural and symbolic execution movable. You can replace a code tool with an agent (when edge cases multiply) or replace an agent with code (when patterns stabilize) without changing the caller's instructions or behavior.

The practical consequence: refactoring between neural and symbolic is a local change, not a system-wide rewrite.

---

Relevant Notes:
- [[related note]] -- extends this by showing the refactoring mechanics

Topics:
- [[architecture-index]]
```

Key points about the note:
- **Title is a proposition**: "agent-as-tool makes callers agnostic to implementation" -- you could disagree with this.
- **Description adds information beyond the title**: it explains the mechanism (cannot distinguish neural from symbolic) and the implication (free movement).
- **Body shows reasoning**: not just the claim but the path to the conclusion.
- **Footer links**: relevant notes with relationship context, topic index membership.

### Step 2: Run the pipeline on your note

After creating a note directly (outside the extract pipeline), connect it to the graph:

```
/arscontexta-connect [[agent-as-tool makes callers agnostic to implementation]]
```

This finds related notes, adds wiki links, and updates the relevant index.

Then verify quality:

```
/arscontexta-review agent-as-tool makes callers agnostic to implementation
```

This runs the cold-read prediction test, schema validation, and health checks.

## Processing Source Material

When you have a design document, research article, or PR discussion worth mining for llm-do insights, use the full pipeline:

### Option A: Step by step

1. Drop the file in `inbox/`
2. `/arscontexta-seed inbox/source-file.md` -- queues it for processing
3. `/arscontexta-extract inbox/source-file.md` -- extracts insights as note candidates
4. Approve the extraction, then run `/arscontexta-connect`, `/arscontexta-revisit`, `/arscontexta-review` on each note

### Option B: Automated

```
/arscontexta-pipeline inbox/source-file.md
```

This chains all four phases automatically, using `/arscontexta-ralph` to spawn fresh-context subagents for each phase.

### Option C: Queue-based batch processing

```
/arscontexta-seed inbox/source-file.md
/arscontexta-ralph 5
```

This seeds the source into the queue, then processes 5 tasks from the queue with isolated subagent contexts.

## Understanding the Queue

The processing queue lives at `ops/queue/queue.json`. Each entry tracks a single note through its lifecycle:

```json
{
  "id": "claim-010",
  "type": "claim",
  "status": "pending",
  "target": "agent-as-tool makes callers agnostic to implementation",
  "current_phase": "create",
  "completed_phases": []
}
```

As each phase completes, `current_phase` advances: create -> connect -> revisit -> review. The `/arscontexta-next` skill reads this queue to recommend what to work on.

## Exploring the Knowledge Graph

Once you have a few notes, explore the graph:

- `/arscontexta-graph health` -- orphan detection, dangling links, link density
- `/arscontexta-graph triangles` -- find synthesis opportunities (two notes that together imply a third)
- `/arscontexta-graph clusters` -- identify topic clusters
- `/arscontexta-stats` -- overall vault metrics

## What to Read Next

- [[skills]] -- Complete reference for all available commands
- [[workflows]] -- Detailed processing pipeline documentation
- [[configuration]] -- How to tune the system via ops/config.yaml
- [[meta-skills]] -- Skills for evolving the system itself
- [[troubleshooting]] -- When things go wrong
