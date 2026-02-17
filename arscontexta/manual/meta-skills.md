---
description: System evolution skills for the llm-do knowledge system -- /arscontexta:ask, /arscontexta:architect, /arscontexta-rethink, /arscontexta-remember
type: manual
generated_from: "arscontexta-0.8.0"
---

# Meta-Skills

Meta-skills operate on the knowledge system itself rather than on individual notes. They capture friction, challenge assumptions, answer methodology questions, and modify system architecture. These are how the system learns and evolves.

## The Self-Evolution Loop

The llm-do knowledge system follows a specific evolution pattern:

```
Work normally
    |
    v
Notice friction (search fails, wrong filing, user correction)
    |
    v
/arscontexta-remember -- capture the friction signal
    |
    v
Accumulate observations (arscontexta/ops/observations/)
    |
    v
Threshold reached (10+ observations)
    |
    v
/arscontexta-rethink -- triage, detect patterns, generate proposals
    |
    v
/arscontexta:architect -- implement structural changes (if needed)
    |
    v
/arscontexta:ask -- verify approach against methodology research
```

**Key principle:** Complexity arrives at pain points, not before. You do not add features because they seem useful -- you add them because you have hit friction.

---

## /arscontexta-remember

**Purpose:** Capture operational friction as methodology notes in arscontexta/ops/observations/ or arscontexta/ops/methodology/.

**Why it matters:** Without explicit friction capture, the same problems recur across sessions. Each session starts cold and rediscovers the same issues. /arscontexta-remember externalizes the learning so future sessions benefit.

### Three Modes

#### Explicit Mode

Directly describe the friction you just experienced.

```
/arscontexta-remember "extraction skips implementation ideas because they are classified as not-claims"
```

This creates an observation note in `arscontexta/ops/observations/` with a prose-sentence title:

```markdown
---
category: process-gap
status: pending
created: 2026-02-16
---

# extraction skips implementation ideas because they are classified as not-claims

[Description of what happened, what was expected, what went wrong]
```

**llm-do examples:**
- `/arscontexta-remember "connect fails to find notes about agent specs when searching for toolset patterns"` -- search vocabulary mismatch
- `/arscontexta-remember "review cold-read prediction is too easy when description restates title"` -- quality gate weakness
- `/arscontexta-remember "pipeline chaining suggests connect but note was already connected manually"` -- state tracking gap

#### Contextual Mode

Run without arguments to review the recent conversation for corrections and patterns.

```
/arscontexta-remember
```

The skill scans recent exchanges for:
- User corrections ("no, that should be..." / "actually..." / "not like that")
- Repeated patterns (doing the same thing three times differently)
- Expressed preferences ("always do X" / "never do Y")

Each discovered pattern becomes an observation note.

#### Session Mining Mode

Scan arscontexta/ops/sessions/ transcript archives for recurring patterns.

```
/arscontexta-remember --mine
```

This is useful after several sessions of llm-do development. It reads session logs and looks for:
- Friction that appeared in multiple sessions
- Corrections that were made repeatedly
- Workflow patterns that emerged organically

### Threshold Alerts

After creating an observation, the skill checks counts:
- If `arscontexta/ops/observations/` has 10+ pending items: suggests running `/arscontexta-rethink`
- If `arscontexta/ops/tensions/` has 5+ pending items: suggests running `/arscontexta-rethink`

These thresholds are configurable in arscontexta/ops/config.yaml.

---

## /arscontexta-rethink

**Purpose:** Challenge system assumptions against accumulated evidence. The scientific method applied to knowledge system evolution.

**When to run:**
- `/arscontexta-next` recommends it (observation/tension thresholds crossed)
- After a significant development milestone in llm-do (architecture change, major refactor)
- When the same friction keeps occurring despite previous captures

### Six Phases

#### Phase 0: Drift Check

Compares arscontexta/ops/config.yaml against arscontexta/ops/derivation.md to detect configuration drift. If dimensions have shifted without a corresponding derivation update, flags the drift.

**llm-do example:** If `processing.depth` was changed from `standard` to `deep` for a specific task but never reverted, drift check surfaces this.

```
/arscontexta-rethink drift
```

#### Phase 1: Triage

Reads all pending observations and tensions. For each:
- Classifies severity (friction, surprise, methodology insight, process gap)
- Determines if it maps to an existing methodology note or needs a new one
- Creates or updates methodology notes in arscontexta/ops/methodology/

```
/arscontexta-rethink triage
```

#### Phase 2: Evidence Gathering

Reads existing methodology notes to understand current system self-knowledge. Builds context for pattern detection.

#### Phase 3: Pattern Detection

Looks across triaged observations for recurring themes:
- Are multiple observations about the same skill? (skill-level issue)
- Are multiple observations about the same phase? (pipeline issue)
- Do observations cluster around a specific llm-do concept area? (domain coverage gap)

#### Phase 4: Proposal Generation

For each detected pattern, generates a concrete improvement proposal:
- What to change (configuration, skill behavior, schema, workflow)
- Expected impact (reduced friction, better coverage, faster processing)
- Risk assessment (what might break)

#### Phase 5: Resolution

Presents proposals for approval. Approved changes are either:
- Applied directly (configuration changes via arscontexta/ops/config.yaml edits)
- Routed to `/arscontexta:architect` (structural changes requiring schema or template modification)
- Deferred (logged as future work in arscontexta/self/goals.md)

### Running Specific Phases

```
/arscontexta-rethink            # full six-phase run
/arscontexta-rethink triage     # Phase 1 only
/arscontexta-rethink patterns   # Phases 3-5 only
/arscontexta-rethink drift      # Phase 0 only
```

---

## /arscontexta:ask

**Purpose:** Answer questions about knowledge system methodology by consulting two knowledge layers.

### Two Knowledge Layers

1. **Local methodology** (arscontexta/ops/methodology/) -- "How does MY system work?" Notes about this specific knowledge system's configuration, learned behaviors, and operational patterns.

2. **Bundled research** -- "Why is this a good idea?" Research-backed methodology notes shipped with the arscontexta engine. These explain the theoretical foundations: why wiki links work, why propositional titles matter, why description quality affects retrieval.

### Usage Patterns

**Understanding configuration rationale:**
```
/arscontexta:ask "why is granularity set to moderate instead of atomic?"
```
Checks arscontexta/ops/derivation.md for the conversation signals, then consults research on granularity trade-offs.

**Exploring methodology questions:**
```
/arscontexta:ask "should I split notes that connect to more than 5 indexes?"
```
Checks local methodology for any existing guidance, then consults research on note composability.

**llm-do-specific questions:**
```
/arscontexta:ask "how should I handle notes about features that were removed from the runtime?"
```
Checks methodology for content staleness guidance, provides recommendations specific to llm-do's evolution pace.

### When to Use /arscontexta:ask vs Reading Directly

| Situation | Approach |
|-----------|----------|
| Quick factual lookup | Read arscontexta/ops/config.yaml or arscontexta/ops/derivation.md directly |
| Understanding WHY a choice was made | /arscontexta:ask -- it synthesizes across sources |
| Exploring a methodology question | /arscontexta:ask -- it consults both local and research knowledge |
| Debugging a skill's behavior | Read the skill's SKILL.md file directly |

---

## /arscontexta:architect

**Purpose:** Modify the knowledge system's structure, schema, or methodology with architectural reasoning.

### What It Can Change

| Change type | Example |
|-------------|---------|
| Schema fields | Add a `complexity` field to note templates for llm-do architectural notes |
| Template structure | Add a "Migration Impact" section to ADR templates |
| Index structure | Split an oversized architecture index into runtime-index and harness-index |
| Navigation hierarchy | Add a new tier for llm-do subsystem documentation |
| Extraction categories | Add "refactoring-patterns" as an extraction category |

### How It Works

1. You describe what you want to change and why
2. The skill analyzes the current system structure (templates, schema, derivation)
3. It generates a plan showing what files change, what the migration path looks like, and what risks exist
4. It applies changes after approval

### When to Use

Use /arscontexta:architect when:
- `/arscontexta-rethink` generates a proposal that requires structural changes
- You want to add domain-specific schema fields for llm-do
- An index has grown past 40 notes and needs splitting
- The extraction categories need adjustment for llm-do's evolving architecture

Do NOT use /arscontexta:architect for:
- Configuration changes (edit arscontexta/ops/config.yaml directly, then `/arscontexta-refactor`)
- Note content changes (use the pipeline skills)
- Public documentation changes (docs/*.md is outside the knowledge system)

---

## Interaction Between Meta-Skills

The meta-skills form a feedback loop:

| When this happens... | ...do this |
|---------------------|-----------|
| You notice friction during llm-do development | `/arscontexta-remember "description"` |
| 10+ observations accumulate | `/arscontexta-rethink` |
| Rethink proposes a config change | Edit arscontexta/ops/config.yaml + `/arscontexta-refactor` |
| Rethink proposes a structural change | `/arscontexta:architect` |
| You question whether a change is sound | `/arscontexta:ask "rationale question"` |
| A structural change is implemented | `/arscontexta:reseed` (regenerate skills for new structure) |

### Anti-Pattern: Productivity Porn

The meta-skills exist to serve llm-do development, not to replace it. Warning signs:

- Running `/arscontexta-rethink` every session when only 2 observations exist
- Using `/arscontexta:architect` to redesign schema before you have 20 notes
- Spending more time on `/arscontexta-remember` than on actual design notes
- Chaining meta-skills without doing library development work between them

**Rule of thumb:** Meta-skill usage should be less than 20% of total session time. The vault serves the library, not the other way around.

See [[skills]] for the complete command reference. See [[configuration]] for the thresholds that trigger meta-skill recommendations. See [[troubleshooting]] for when meta-skills surface unexpected results.
