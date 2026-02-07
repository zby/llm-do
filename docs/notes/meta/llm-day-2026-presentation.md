---
description: LLM Day 2026 Warsaw conference presentation proposal
---

# LLM Day 2026 Warsaw - Presentation Proposal

---

## CFP Submission Materials

### Title Options (undecided)

- "Recursive Isn't Enough: Unifying LLM and Code for Reliable Systems"
- "Stabilize the Joints: A Unified Interface for LLM and Code"
- "One Interface, Two Engines: LLM + Code Without Rewrites"
- "Same Call, Different Engine: Unifying Stochastic and Deterministic"

### Elevator Pitch (300 chars)

> Recursive execution is necessary but not sufficient. Reliability fails at the joints—contracts get violated, pipelines break. llm-do unifies LLM and code under one interface so you can progressively stabilize boundaries into reliable code while keeping flexibility where you need it.

### Description

> This talk introduces a model for building reliable systems on stochastic foundations. We treat LLMs as stochastic computers: they don't produce outputs, they sample from distributions. The boundaries between components are where variance collapses or expands—and crucially, where you can intervene.
>
> Using llm-do, we show how a unified calling convention enables fluid refactoring between LLM and code. The same call site works whether the implementation is a prompt or a function. This makes stabilizing cheap: as patterns stabilize, extract them to code. Keep flexibility where requirements are fuzzy; make the joints reliable.
>
> We'll walk through concrete examples showing the progression from all-LLM prototype to production-ready system with stabilized boundaries—and demonstrate how the same patterns let you soften components back to LLM when requirements change.
>
> Attendees will leave with a coherent mental model for LLM system reliability and practical patterns for taking applications from prototype to production.

### Notes (for reviewers only)

> **Speaker background:**
> I have over 20 years of experience as a software developer. I'm approaching LLM applications not as an AI specialist but as an engineer who's seen this pattern before: new technology arrives, teams build fragile systems, and eventually the field rediscovers that composition, contracts, and boundaries matter. This talk applies hard-won software engineering principles to LLM systems.
>
> **Why this talk:**
> This isn't a framework pitch. The conceptual model (stochastic computers, boundary stabilizing) stands independent of llm-do—the tool just makes the patterns concrete. The insight that composition boundaries are the failure points comes from decades of building distributed systems and watching integration points fail. LLM systems have the same disease; they need the same cure.
>
> **Talk maturity:**
> The presentation structure is complete. llm-do is open source with working examples demonstrating the stabilizing progression.
>
> **Technical requirements:**
> Standard presentation setup (HDMI/USB-C, slides). Live demo optional—can be pre-recorded or replaced with annotated code walkthrough if preferred.
>
> **Audience fit:**
> Aimed at developers building LLM applications who've hit the prototype-to-production gap. The concepts are language-agnostic but examples are in Python—basic Python familiarity required. No framework-specific knowledge required.

### Bio

> Zbigniew Lukasiak has been building software since the dot-com era. He's worked across startups, large corporations, and academia—including the University of London, where he helped build PhilPapers, a comprehensive index of philosophy research used by academics worldwide.
>
> Having witnessed the birth of the web, he sees the same energy in LLMs today—and the same patterns of fragile early systems that eventually need engineering discipline. He's the author of llm-do, an open-source framework for building reliable LLM applications through progressive stabilizing.

---

## Original Title

**"Stochastic Computers: Building Reliable Systems on Unreliable Foundations"**

*(Subtitle: How llm-do enables fluid refactoring between stochastic and deterministic execution)*

## Through-line

> "Recursive execution is necessary but not sufficient; reliability comes from being able to refactor fluidly between stochastic and deterministic—and llm-do makes that refactoring cheap."

Every slide returns to this.

---

## Structure (Rule of Three)

### Part 1: The Problem (5 min)

**Slide 1: "Recursive Isn't Enough"**
- Recursive execution shows compositionality, but doesn't solve reliability
- Pure prompts: flexible but fragile (can't test, can't debug)
- Pure code: reliable but brittle (edge cases explode)
- Graph DSLs: structure but friction (refactoring = redrawing)

**So what:** Teams get stuck at prototypes. Production feels risky.

**Slide 2: "Why It's Hard"**
- The real issue: we're treating stochastic systems as if they were deterministic
- Same prompt → different behavior (not a bug—intrinsic)
- Failures cluster at boundaries between components, not inside them

**Transition:** "What if we took the stochasticity seriously instead of fighting it?"

---

### Part 2: The Theory (7 min)

**Slide 3: Diagram 1 — "Specs → Distributions"**

```
┌─────────────────────────────────────────┐
│  Traditional:  Program → Output         │
│  Stochastic:   Spec → Distribution      │
│                       ↓                 │
│                 [sample behavior]       │
└─────────────────────────────────────────┘
```

- A prompt doesn't pick a behavior—it shapes a distribution over behaviors
- Temperature makes this explicit; it's always there

**So what:** "Tests become invariants + sampling, not equality assertions."

**Slide 4: Diagram 2 — "Distribution Boundaries" (progressive reveal)**

Build in 3 steps:
1. Show: `LLM` (distribution)
2. Add: `LLM → Tool` (variance collapses)
3. Complete: `LLM → Tool → LLM` (variance reintroduced)

```
Step 3:
  Stochastic → Deterministic → Stochastic
     (LLM)        (tool)         (LLM)
  distribution   point mass    distribution
       ↓            ↓              ↓
   [variance]   [checkpoint]   [variance]
```

**So what:** "Boundaries are refactoring points. They're where you can intervene—with approvals, logging, validation, or by moving logic across."

**Slide 5: "The Key Insight"**

> "The boundary exists whether you see it or not. llm-do makes it visible—and lets you move logic across it freely."

*(Pause. Let this land.)*

---

### Part 3: Implementation in llm-do (10 min)

**Slide 6: "Unified Calling Convention"**

Show the single code snippet (3 lines):

```python
# Today: LLM handles classification
result = await ctx.call("ticket_classifier", ticket_text)

# Tomorrow: stabilized to Python (same call site)
result = await ctx.call("ticket_classifier", ticket_text)
```

*(Freeze 10 sec. Highlight: the call site doesn't change.)*

**So what:** "Same call site, different implementation. Refactoring is cheap."

**Slide 7: Diagram 3 — "The Stabilizing Slider"**

```
Soften                                    Stabilize
   ↓                                         ↓
┌─────────────────────────────────────────────┐
│  Stochastic ◄─────────────────► Deterministic │
│  (flexible)                      (testable)   │
└─────────────────────────────────────────────┘
        │                              │
   "Add capability               "Extract stable
    via spec"                     patterns to code"
```

- Stabilize when patterns stabilize
- Soften when you need flexibility
- Move in both directions as requirements evolve

**So what:** "Start stochastic where you need flexibility. Stabilize as patterns emerge. The unified interface makes this movement natural."

**Slide 8: "What Changes When You Stabilize"**

| Aspect | Stochastic | Stabilized |
|--------|------------|----------|
| Testing | Sample N times, check invariants | Assert equality |
| Approvals | Needed per call | Trusted (it's your code) |
| Performance | API calls, seconds | Microseconds |
| Auditability | Opaque reasoning | Full trace |

**So what:** "Every piece you stabilize becomes traditionally testable. Progressive stabilizing = progressive confidence."

**Slide 9: "The Harness Pattern"**

- Your code owns control flow (or LLM does—your choice)
- llm-do intercepts at the tool layer
- Approvals = syscalls (block until permission granted)
- Call sites stay stable; implementations move across the boundary

**Slide 10: Live Example** *(if time/format allows)*

Quick demo: file_organizer or pitchdeck_eval showing the stabilizing progression:
- `pitchdeck_eval` — All LLM
- `pitchdeck_eval_stabilized` — Extracted `list_pitchdecks()` to Python
- `pitchdeck_eval_code_entry` — Python orchestration, LLM only for analysis

---

### Close (3 min)

**Slide 11: "The Recipe"**

1. Treat recursion as a baseline, not the finish line
2. Model LLMs as stochastic computers (not fuzzy deterministic ones)
3. Make distribution boundaries explicit (that's where you can refactor)
4. Use a unified calling convention (so refactoring is cheap)
5. Stabilize progressively (start flexible, extract determinism as patterns emerge)

**Slide 12: "One Slide Summary"**

> "Recursive execution is necessary but not sufficient. Reliability comes from fluid refactoring between stochastic and deterministic. llm-do makes that refactoring cheap."

**Slide 13: Resources**

- GitHub: [link]
- theory.md: formal treatment of stochastic computation
- architecture.md: internal structure and design
- reference.md: API and workflows
- examples/: stabilizing progression demos

---

## Presentation Tactics

### Code Strategy

- **Only one code snippet** shown (the `ctx.call` example)
- 3 lines, same call site, different implementation behind it
- Freeze and let them read
- Highlight the unchanged line

### Diagram Summary

| # | Concept | Build Strategy |
|---|---------|----------------|
| 1 | Spec → Distribution | Static, simple |
| 2 | Distribution Boundaries | Progressive (3 steps) |
| 3 | Stabilize/Soften Slider | Static with annotations |

### "So What?" Callouts

| After... | So what |
|----------|---------|
| Stochastic computers | Tests are invariants + sampling, not equality |
| Boundaries | Refactoring points where you can intervene |
| Unified calling | Same call site, different implementation |
| Stabilizing | Progressive confidence, more testable surface |

---

## Timing Estimate

| Part | Minutes |
|------|---------|
| Problem | 5 |
| Theory | 7 |
| Implementation | 10 |
| Close + Q&A buffer | 3 |
| **Total** | **25** |

---

## Key Messages to Land

1. **Stochasticity is intrinsic** — not a bug to fix, a property to work with
2. **Boundaries matter** — they're where variance enters/collapses, and where you refactor
3. **Unified calling enables movement** — same interface for stochastic and deterministic means cheap refactoring
4. **Progressive stabilizing** — start flexible, extract determinism as patterns emerge, move both directions

## What Makes This Different

- Not "how to prompt better"
- Not "here's another agent framework"
- Instead: a coherent model for building reliable systems on stochastic foundations, with a practical implementation that makes the theory actionable
