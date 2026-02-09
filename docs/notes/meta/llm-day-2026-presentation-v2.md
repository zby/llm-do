# LLM Day 2026 Warsaw - Presentation Plan v2

## Two Roads to Recursive Dispatch

**Duration**: 30 minutes (25 content + 5 Q&A)

---

## Through-line

> "Two independent motivations—power and evolvability—both require recursive dispatch between LLM and code. They diverge on design: RLMs optimize for power with an explicit boundary. llm-do optimizes for evolution with a unified calling convention, enabling systems that grow from prototype to production."

---

## Title Options

- **"Two Roads to Recursive Dispatch: Power and Evolution in LLM-Code Systems"** (selected)
- "Extend, Stabilize, Recurse: A Unified Interface for LLM and Code"
- "The Breathing System: Progressive Stabilization for LLM Applications"

---

## Structure Overview

| Part | Topic | Time |
|------|-------|------|
| 1 | The Vision: Extending Systems by Prompting | 4 min |
| 2 | Two Roads to the Same Design | 6 min |
| 3 | The Convergence: What Both Require | 3 min |
| 4 | The Concrete Demo | 5 min |
| 5 | The Theoretical Frame | 5 min |
| 6 | Close & Takeaways | 3 min |
| | Q&A | 5 min |
| | **Total** | **31 min** |

---

## Part 1: The Vision (4 min)

### Slide 1: Title Slide

**"Two Roads to Recursive Dispatch"**
*Power and Evolution in LLM-Code Systems*

Zbigniew Lukasiak
LLM Day 2026, Warsaw

---

### Slide 2: The Dream

> "Imagine a computer you extend by talking to it."

**The workflow:**
1. You describe what you want → LLM does it (like a copilot)
2. You save that prompt → it becomes a named capability
3. You use it repeatedly → observe what's stable
4. You encode stable parts as code → hybrid capability

**Visual**: Simple flow diagram showing this progression

**So what**: "This is how software should grow—organically, from intent to implementation."

---

### Slide 3: The Problem With This Dream

But when you try to build it:

- Saved prompts and code have different interfaces
- Refactoring from prompt → code breaks call sites
- No unified way to compose them
- Where does the LLM end and code begin?

**So what**: "The dream requires an architecture that doesn't exist in standard LLM frameworks."

---

## Part 2: Two Roads (6 min)

### Slide 4: "I Wasn't Alone"

> "When I started thinking about what this system needs, I found others arriving at the same place from a different direction—but with a different priority."

Two independent motivations. Same structural need. Different values.

---

### Slide 5: Road 1 — Evolvability (My Origin)

**The goal**: Systems that grow and mature over time

```
User describes intent
        ↓
LLM performs it
        ↓
Save as named capability
        ↓
Observe patterns over time
        ↓
Encode stable parts as code
        ↓
Hybrid capability (prompt + code)
```

**The priority**: Not maximum power at any moment—but enabling the system to **evolve**.
Refactoring from prompt to code must be cheap. The engineering lifecycle matters.

**What this requires**:
- Save prompts as callable units
- Unified interface (prompts and code look the same)
- Progressive stabilization (move logic prompt → code without breaking callers)

---

### Slide 6: Road 2 — Power (RLM Perspective)

**The goal**: Maximum expressive power through recursion

- Code: deterministic, fast, cheap—but rigid
- Prompts: flexible, handle ambiguity—but expensive, variable
- **Neither dominates**—each is better for different subtasks

**The recursive insight** (this is also the neuro-symbolic completeness argument):

```
Task (ambiguous → LLM)
├── Subtask A (mechanical → code)
├── Subtask B (judgment → LLM)
│   ├── Sub-B1 (lookup → code)
│   └── Sub-B2 (creative → LLM)
└── Subtask C (formatting → code)
```

At any depth, choose the best execution mode for that subtask.
Full power requires arbitrary interleaving: `LLM → code → LLM → code → ...`

**The priority**: Solve harder problems. The architecture serves capability at a point in time.

**What this requires**:
- Recursive dispatch between LLM and code
- Mode choice independent of nesting depth
- Calling convention (explicit or unified)

---

### Slide 7: RLMs and llm-do — Different Priorities

Recursive Language Models (Prime Intellect, Oct 2025):
- **Priority: power** — solve harder problems through recursive decomposition
- Models manage their own context, delegate to Python scripts and sub-LLMs
- **Explicit boundary**: LLM calls and code calls have different APIs
- **Pure computation**: no user approvals — simplifies architecture significantly
- The architecture serves capability at a point in time

llm-do:
- **Priority: evolution** — systems that grow and mature over time
- Same recursive power, but **unified calling convention**: LLM and code calls look identical
- **Coding-agent path**: full approval/safety harness for dangerous tool calls
- The architecture serves the engineering lifecycle — refactoring, testing, incremental improvement

**Different values, not just different features.** If you optimize for power, an explicit boundary is fine — you're not planning to move things across it. If you optimize for evolution, refactoring cost is everything.

---

### Slide 8: The Convergence Diagram

```
        EVOLVABILITY                     POWER
              │                                │
       "systems that                  "use the best tool
        grow and mature"               for each subtask,
                                        at any depth"
              │                                │
              └────────────────┬───────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  RECURSIVE DISPATCH │
                    │  (both roads need)  │
                    └─────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
    ┌───────────────────┐             ┌───────────────────┐
    │  RLM:             │             │  llm-do:          │
    │  explicit boundary│             │  unified calling  │
    │  pure computation │             │  approval harness │
    └───────────────────┘             └───────────────────┘
              │                                 │
              ▼                                 ▼
    ┌───────────────────┐             ┌───────────────────┐
    │  max capability   │             │    PROGRESSIVE    │
    │  at a point in    │             │   STABILIZATION   │
    │  time             │             │  (system evolves) │
    └───────────────────┘             └───────────────────┘
```

*(Build this progressively: convergence point, then two approaches, then outcomes)*

---

## Part 3: The Convergence (3 min)

### Slide 9: Shared Requirement, Different Priorities

**Both roads require**: Recursive dispatch between LLM and code

**RLMs**: Power first — explicit boundary, pure computation, maximum capability

**llm-do**: Evolution first — unified boundary, approval harness, cheap refactoring

| | RLM | llm-do |
|---|-----|--------|
| **Priority** | **Power** | **Evolution** |
| Recursive dispatch | ✓ | ✓ |
| Boundary visibility | Explicit | Hidden |
| User approvals | None (pure computation) | Full harness (coding-agent style) |
| Refactoring cost | Pay the tax | No changes |
| Progressive stabilization | Not a goal | Core design driver |

**So what**: "Same recursive power, different values. RLMs ask 'what can we solve?' llm-do asks 'how does this system mature?'"

---

### Slide 10: llm-do's Design Choice

> "Whether a capability is neural (LLM) or symbolic (code) should be invisible at the call site."

This follows directly from the evolution priority. If your system is going to change over time—logic moving from LLM to code and back—the boundary must be cheap to cross.

This is an engineering choice, not a research choice. It enables:
- Refactoring without breaking callers
- Progressive stabilization as patterns emerge
- Experimentation: swap implementations freely
- The standard engineering lifecycle applied to hybrid systems

*(Pause. Let this land.)*

---

## Part 4: The Concrete Demo (5 min)

### Slide 11: Let's See It Work — Data Report Generator

**The caller** (`main.agent`) — identical in both versions:

```
1. Use list_files("input", "*.csv") to find all CSV files.
2. For each CSV file:
   - Call analyze_dataset(path=<csv_path>)
   - Write the returned report to reports/<name>.md
```

The caller never changes. Only the implementation of `analyze_dataset` evolves.

---

### Slide 12: Version 1 — All LLM (Prototype)

`examples/data_report/analyze_dataset.agent`:

```
You are a data analyst. You will receive a path to a CSV file.
1. Read the CSV file using read_file(path).
2. Compute summary statistics (mean, median, min, max).
3. Identify notable trends.
4. Write a narrative report with statistics, interpretation,
   and recommendations.
```

**What the LLM is doing**:
- Reading and parsing CSV (mechanical)
- Computing statistics (mechanical)
- Identifying trends (reasoning)
- Writing narrative (reasoning)

**Problem**: LLM computes averages — expensive, sometimes wrong. This is calculator work.

---

### Slide 13: Version 2 — Hybrid (Stabilized)

`examples/data_report_stabilized/tools.py`:

```python
async def analyze_dataset(ctx, path: str) -> str:
    rows = list(csv.DictReader(open(path)))      # Code (mechanical)
    stats = compute_summary(rows)                # Code (mechanical)
    trends = detect_trends(rows)                 # Code (mechanical)

    narrative = await ctx.deps.call_agent(       # LLM (reasoning)
        "write_narrative",
        {"input": f"Stats: {stats}\nTrends: {trends}"}
    )
    return format_report(stats, narrative)       # Code (mechanical)
```

**Same call. Same name. Same arguments.** The caller never knew it changed.
Code handles what's mechanical. LLM handles what needs interpretation.

---

## Part 5: The Theoretical Frame (5 min)

### Slide 14: Why This Works — Distribution Boundaries

LLM components sample from distributions.
Code components are point masses (deterministic).

```
Stochastic  →  Deterministic  →  Stochastic
   (LLM)          (tool)           (LLM)
distribution    point mass      distribution
     ↓              ↓               ↓
 [variance]    [checkpoint]     [variance]
```

**Boundaries are natural intervention points**:
- Approvals (gate the call)
- Logging (observe what flows through)
- Testing (mock the implementation)
- **Refactoring** (move logic across)

---

### Slide 15: Stabilizing and Softening

```
         ◄─────── SOFTEN ────────
         (add flexibility back)

Stochastic ─────────────────────► Deterministic
(flexible,                         (testable,
 handles ambiguity)                 fast, cheap)

         ─────── STABILIZE ──────►
         (extract patterns to code)
```

**Stabilize** when:
- Patterns emerge (you see the LLM doing the same thing every time)
- You need reliability (same input → same output)
- Cost/latency matters

**Soften** when:
- Edge cases multiply (code too rigid)
- Requirements are fuzzy (don't know exact behavior yet)
- You need to extend capability quickly

**The system breathes.** Logic moves in both directions as requirements evolve.

---

### Slide 16: What Changes When You Stabilize

| Aspect | Stochastic (LLM) | Stabilized (Code) |
|--------|------------------|-------------------|
| **Testing** | Sample N times, check invariants | Assert equality |
| **Performance** | API calls, seconds | Microseconds |
| **Cost** | Tokens per call | Zero marginal cost |
| **Auditability** | Opaque reasoning | Full trace |
| **Approvals** | May need human review | Trusted (your code) |

**So what**: "Every piece you stabilize becomes traditionally testable. Progressive stabilization = progressive confidence."

---

### Slide 17: The Harness Pattern

Tool calls are intercepted like syscalls:

```
Agent/Code ──→ Harness ──→ Tool execution
                  │
           (approval check)
           (logging)
           (validation)
```

- **Approvals** block until permission granted
- **Observability** via message history, usage tracking
- **Your code owns control flow** (or LLM does—your choice)

---

## Part 6: Close (3 min)

### Slide 18: The Recipe

1. **Unify the calling convention** — LLM and code share the same interface
2. **Enable recursive dispatch** — neural and symbolic can call each other at any depth
3. **Stabilize progressively** — start stochastic, extract determinism as patterns emerge
4. **Keep the boundary visible** — that's where you refactor, test, and intervene

---

### Slide 19: What Makes This Different

**Not**:
- "How to prompt better"
- "Another agent framework"
- "Graphs are the answer"

**Instead**:
- An engineering approach to hybrid systems — optimizing for evolution, not just power
- Architecture derived from two independent motivations (power and evolvability)
- Practical implementation that makes progressive stabilization cheap

---

### Slide 20: The Tradeoffs (Honest)

**Good fit**: prototyping with progressive stabilization, Python control flow, refactoring between LLM and code

**Poor fit**: durable workflows with checkpointing, distributed orchestration, graph-based visualization

**Current status**: Research-grade. The concepts are more mature than the implementation.

---

### Slide 21: One Slide Summary

> "Two roads—power and evolvability—both need recursive dispatch. RLMs optimize for power. llm-do optimizes for evolution, making the engineering lifecycle work for hybrid systems."

> "Start stochastic for flexibility. Stabilize as patterns emerge. The unified interface makes this movement cheap."

---

### Slide 22: Resources

- **GitHub**: github.com/zby/llm-do
- **Theory**: `docs/theory.md` — stochastic computation model
- **Architecture**: `docs/architecture.md` — internal structure
- **Examples**: `examples/data_report*` — stabilization progression

Questions?

---

## Presentation Tactics

### Code Strategy

- **Minimal code on slides** — only the essential lines
- Freeze for 10 seconds, let them read
- Highlight unchanged lines to show interface stability
- Pre-syntax-highlighted, large font

### Diagram Strategy

| Slide | Diagram | Build Strategy |
|-------|---------|----------------|
| 8 | Convergence | Progressive (two roads → requirements → conclusion) |
| 14 | Distribution boundaries | Progressive (LLM → tool → LLM) |
| 15 | Stabilize/Soften | Static with bidirectional arrows |

### "So What?" Moments

| After... | So what |
|----------|---------|
| The dream | "This is how software should grow" |
| Two roads | "Same need, different values — power vs. evolution" |
| Convergence | "The unified boundary follows from the evolution priority" |
| Data report demo | "Same call, same name — the caller never knew it changed" |
| Stabilization table | "Progressive stabilization = progressive confidence" |

### Demo Option

If live demo is possible:
1. Run `data_report` — LLM does everything (stats + narrative)
2. Run `data_report_stabilized` — code does stats, LLM only writes narrative

Show the output side by side: V2 has deterministic stats tables (code) followed by LLM narrative. The numbers tell the story better than slides.

---

## Backup Slides

### Backup 1: File Organizer Example

Alternative demo showing semantic/mechanical separation:
- LLM decides what files should be called (semantic)
- Python sanitizes filenames (mechanical)

### Backup 2: The Entry Point Patterns

Three orchestration styles:
1. Agent entry (LLM orchestrates)
2. Code entry (Python orchestrates)
3. Orchestrating tool (encapsulated workflow)

### Backup 3: Comparison to LangGraph

| Aspect | Graph DSLs | llm-do |
|--------|------------|--------|
| Control flow | Declarative (nodes/edges) | Imperative (Python) |
| Refactoring | Redraw the graph | Change code |
| Mental model | Dataflow | Function calls |
| State | Global context | Local scope |

---

## CFP Materials (Updated)

### Title

**"Two Roads to Recursive Dispatch: Power and Evolution in LLM-Code Systems"**

### Elevator Pitch (300 chars)

> Power and evolvability both require recursive dispatch between LLM and code. RLMs optimize for power; llm-do optimizes for evolution — enabling systems that grow by prompting and stabilize to code as patterns emerge.

### Description

> This talk presents a unified architecture for LLM-based systems, derived from two independent motivations that converge on the same structural need but diverge on priorities.
>
> First, the evolvability road—systems you extend by talking to them, saving prompts as capabilities, and progressively stabilizing to code. The priority is the engineering lifecycle: how does this system mature? Second, the power road (building on RLM insights)—at any level of task decomposition, use whichever execution mode (LLM or code) is best for that subtask, requiring arbitrary interleaving of neural and symbolic computation. The priority is maximum capability.
>
> Both roads require recursive dispatch between LLM and code. RLMs optimize for power with explicit boundaries and pure computation—no user approvals, simpler architecture. llm-do optimizes for evolution with a unified calling convention, making the boundary invisible at call sites, and a full approval harness in the style of coding agents. The unified boundary follows from the evolution priority: if your system is going to change over time, refactoring cost is everything.
>
> We demonstrate this with llm-do, showing concrete refactoring from all-LLM prototypes to hybrid systems—without changing call sites. Attendees will leave with practical patterns for organic system evolution from prototype to production.
>
> Note: llm-do's API is currently unstable. The concepts are more mature than the implementation.

### Bio

> Zbigniew Lukasiak has been building software since the dot-com era. He's worked across startups, large corporations, and academia—including the University of London, where he helped build PhilPapers, a comprehensive index of philosophy research used by academics worldwide.
>
> Having witnessed the birth of the web, he sees the same energy in LLMs today—and the same need for architectural discipline. He's the author of llm-do, an open-source hybrid VM for LLM applications that enables progressive stabilization from prototype to production.
