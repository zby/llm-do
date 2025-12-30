# LLM Day 2026 Warsaw - Presentation Proposal

## Title

**"Stochastic Computers: Building Reliable Systems on Unreliable Foundations"**

*(Subtitle: How llm-do enables fluid refactoring between stochastic and deterministic execution)*

## Through-line

> "LLM systems are stochastic; reliability comes from being able to refactor fluidly between stochastic and deterministic—and llm-do makes that refactoring cheap."

Every slide returns to this.

---

## Structure (Rule of Three)

### Part 1: The Problem (5 min)

**Slide 1: "The Wall"**
- Pure prompts: flexible but fragile (can't test, can't debug)
- Pure code: reliable but brittle (edge cases explode)
- Graph DSLs: structure but friction (refactoring = redrawing)

**So what:** Teams get stuck at prototypes. Production feels risky.

**Slide 2: "Why It's Hard"**
- The real issue: we're treating stochastic systems as if they were deterministic
- Same prompt → different behavior (not a bug—intrinsic)

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

# Tomorrow: hardened to Python (same call site)
result = await ctx.call("ticket_classifier", ticket_text)
```

*(Freeze 10 sec. Highlight: the call site doesn't change.)*

**So what:** "Same call site, different implementation. Refactoring is cheap."

**Slide 7: Diagram 3 — "The Hardening Slider"**

```
Soften                                    Harden
   ↓                                         ↓
┌─────────────────────────────────────────────┐
│  Stochastic ◄─────────────────► Deterministic │
│  (flexible)                      (testable)   │
└─────────────────────────────────────────────┘
        │                              │
   "Add capability               "Extract stable
    via spec"                     patterns to code"
```

- Harden when patterns stabilize
- Soften when you need flexibility
- Move in both directions as requirements evolve

**So what:** "Start stochastic where you need flexibility. Harden as patterns emerge. The unified interface makes this movement natural."

**Slide 8: "What Changes When You Harden"**

| Aspect | Stochastic | Hardened |
|--------|------------|----------|
| Testing | Sample N times, check invariants | Assert equality |
| Approvals | Needed per call | Trusted (it's your code) |
| Performance | API calls, seconds | Microseconds |
| Auditability | Opaque reasoning | Full trace |

**So what:** "Every piece you harden becomes traditionally testable. Progressive hardening = progressive confidence."

**Slide 9: "The Harness Pattern"**

- Your code owns control flow (or LLM does—your choice)
- llm-do intercepts at the tool layer
- Approvals = syscalls (block until permission granted)
- Call sites stay stable; implementations move across the boundary

**Slide 10: Live Example** *(if time/format allows)*

Quick demo: file_organizer or pitchdeck_eval showing the hardening progression:
- `pitchdeck_eval` — All LLM
- `pitchdeck_eval_hardened` — Extracted `list_pitchdecks()` to Python
- `pitchdeck_eval_code_entry` — Python orchestration, LLM only for analysis

---

### Close (3 min)

**Slide 11: "The Recipe"**

1. Model LLMs as stochastic computers (not fuzzy deterministic ones)
2. Make distribution boundaries explicit (that's where you can refactor)
3. Use a unified calling convention (so refactoring is cheap)
4. Harden progressively (start flexible, extract determinism as patterns emerge)

**Slide 12: "One Slide Summary"**

> "LLM systems are stochastic. Reliability comes from fluid refactoring between stochastic and deterministic. llm-do makes that refactoring cheap."

**Slide 13: Resources**

- GitHub: [link]
- theory.md: formal treatment of stochastic computation
- concept.md: applied design guide
- examples/: hardening progression demos

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
| 3 | Harden/Soften Slider | Static with annotations |

### "So What?" Callouts

| After... | So what |
|----------|---------|
| Stochastic computers | Tests are invariants + sampling, not equality |
| Boundaries | Refactoring points where you can intervene |
| Unified calling | Same call site, different implementation |
| Hardening | Progressive confidence, more testable surface |

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
4. **Progressive hardening** — start flexible, extract determinism as patterns emerge, move both directions

## What Makes This Different

- Not "how to prompt better"
- Not "here's another agent framework"
- Instead: a coherent model for building reliable systems on stochastic foundations, with a practical implementation that makes the theory actionable
