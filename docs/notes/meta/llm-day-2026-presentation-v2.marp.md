---
marp: true
theme: default
paginate: true
style: |
  section {
    font-size: 28px;
  }
  section.title {
    text-align: center;
    font-size: 32px;
  }
  section.title h1 {
    font-size: 48px;
  }
  pre {
    font-size: 20px;
  }
  table {
    font-size: 24px;
  }
  blockquote {
    font-size: 30px;
    border-left: 4px solid #666;
    padding-left: 1em;
    font-style: italic;
  }
---

<!-- _class: title -->

# Two Roads to Recursive Dispatch

*Power and Evolution in LLM-Code Systems*

**Zbigniew Lukasiak**
LLM Day 2026, Warsaw

---

## The Dream

> "Imagine a computer you extend by talking to it."

**The workflow:**

1. You describe what you want &rarr; LLM does it (like a copilot)
2. You save that prompt &rarr; it becomes a named capability
3. You use it repeatedly &rarr; observe what's stable
4. You encode stable parts as code &rarr; hybrid capability

**This is how software should grow — organically, from intent to implementation.**

<!--
So what: "This is how software should grow—organically, from intent to implementation."
Visual: Simple flow diagram showing this progression
-->

---

## The Problem With This Dream

But when you try to build it:

- Saved prompts and code have **different interfaces**
- Refactoring from prompt &rarr; code **breaks call sites**
- No unified way to **compose** them
- Where does the LLM end and code begin?

**The dream requires an architecture that doesn't exist in standard LLM frameworks.**

---

## "I Wasn't Alone"

> "When I started thinking about what this system needs, I found others arriving at the same place from a different direction — but with a different priority."

Two independent motivations. Same structural need. **Different values.**

---

## Road 1 — Evolvability (My Origin)

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

**The priority**: Not maximum power at any moment — but enabling the system to **evolve**.

**What this requires**: Unified interface. Progressive stabilization. Cheap refactoring.

---

## Road 2 — Power (RLM Perspective)

**The goal**: Maximum expressive power through recursion

- Code: deterministic, fast, cheap — but rigid
- Prompts: flexible, handle ambiguity — but expensive, variable
- **Neither dominates** — each is better for different subtasks

**The recursive insight:**

```
Task (ambiguous → LLM)
├── Subtask A (mechanical → code)
├── Subtask B (judgment → LLM)
│   ├── Sub-B1 (lookup → code)
│   └── Sub-B2 (creative → LLM)
└── Subtask C (formatting → code)
```

Full power requires arbitrary interleaving: `LLM → code → LLM → code → ...`

---

## RLMs and llm-do — Different Priorities

**Recursive Language Models** (Prime Intellect, Oct 2025):
- **Priority: power** — recursive decomposition
- Explicit boundary: LLM calls and code calls have different APIs
- Pure computation: no user approvals

**llm-do:**
- **Priority: evolution** — systems that grow over time
- **Unified calling convention**: LLM and code calls look identical
- Full approval/safety harness for dangerous tool calls

**Different values, not just different features.** If you optimize for power, an explicit boundary is fine. If you optimize for evolution, refactoring cost is everything.

---

## The Convergence

```
     EVOLVABILITY                          POWER
          │                                  │
          └──────────────┬───────────────────┘
                         ▼
              ┌─────────────────────┐
              │  RECURSIVE DISPATCH │
              │  (both roads need)  │
              └─────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
   ┌──────────────┐            ┌──────────────┐
   │ RLM:         │            │ llm-do:      │
   │ explicit     │            │ unified      │
   │ boundary     │            │ calling conv │
   └──────────────┘            └──────────────┘
          │                             │
          ▼                             ▼
   ┌──────────────┐            ┌──────────────┐
   │ max capable  │            │ progressive  │
   │ at a point   │            │ stabiliz-    │
   │ in time      │            │ ation        │
   └──────────────┘            └──────────────┘
```

<!-- Build this progressively: convergence point, then two approaches, then outcomes -->

---

## Shared Requirement, Different Priorities

**Both roads require**: Recursive dispatch between LLM and code

|                            | RLM               | llm-do                      |
|----------------------------|--------------------|-----------------------------|
| **Priority**               | **Power**          | **Evolution**               |
| Recursive dispatch         | ✓                  | ✓                           |
| Boundary visibility        | Explicit           | Hidden                      |
| User approvals             | None               | Full harness                |
| Refactoring cost           | Pay the tax        | No changes                  |
| Progressive stabilization  | Not a goal         | Core design driver          |

**RLMs ask "what can we solve?" llm-do asks "how does this system mature?"**

---

## llm-do's Design Choice

> "Whether a capability is neural (LLM) or symbolic (code) should be invisible at the call site."

This follows directly from the evolution priority. If your system is going to change over time — logic moving from LLM to code and back — the boundary must be cheap to cross.

This is an **engineering choice**, not a research choice. It enables:

- Refactoring without breaking callers
- Progressive stabilization as patterns emerge
- Experimentation: swap implementations freely
- The standard engineering lifecycle applied to hybrid systems

<!-- Pause. Let this land. This is the core design thesis. -->

---

## Let's See It Work — Data Report Generator

**The caller** (`main.agent`) — identical in both versions:
```
1. Use list_files("input", "*.csv") to find all CSV files.
2. For each CSV file:
   - Call analyze_dataset(path=<csv_path>)
   - Write the returned report to reports/<name>.md
```

The caller never changes. Only the implementation of `analyze_dataset` evolves.

---

## Version 1 — All LLM (Prototype)

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
- Reading and parsing CSV *(mechanical)*
- Computing statistics *(mechanical)*
- Identifying trends *(reasoning)*
- Writing narrative *(reasoning)*

**Problem**: LLM computes averages — expensive, sometimes wrong. This is calculator work.

---

## Version 2 — Hybrid (Stabilized)

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

## Why This Works — Distribution Boundaries

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

## Stabilizing and Softening

```
         ◄─────── SOFTEN ────────
         (add flexibility back)

Stochastic ─────────────────────► Deterministic
(flexible,                         (testable,
 handles ambiguity)                 fast, cheap)

         ─────── STABILIZE ──────►
         (extract patterns to code)
```

**Stabilize** when: patterns emerge, you need reliability, cost/latency matters

**Soften** when: edge cases multiply, requirements are fuzzy, you need to extend quickly

**The system breathes.** Logic moves in both directions as requirements evolve.

---

## What Changes When You Stabilize

| Aspect           | Stochastic (LLM)            | Stabilized (Code)     |
|------------------|-----------------------------|-----------------------|
| **Testing**      | Sample N times, check invariants | Assert equality  |
| **Performance**  | API calls, seconds          | Microseconds          |
| **Cost**         | Tokens per call             | Zero marginal cost    |
| **Auditability** | Opaque reasoning            | Full trace            |
| **Approvals**    | May need human review       | Trusted (your code)   |

**Every piece you stabilize becomes traditionally testable.**
**Progressive stabilization = progressive confidence.**

---

## The Harness Pattern

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
- **Your code owns control flow** (or LLM does — your choice)

---

## The Recipe

1. **Unify the calling convention** — LLM and code share the same interface
2. **Enable recursive dispatch** — neural and symbolic can call each other at any depth
3. **Stabilize progressively** — start stochastic, extract determinism as patterns emerge
4. **Keep the boundary visible** — that's where you refactor, test, and intervene

---

## What Makes This Different

**Not**:
- "How to prompt better"
- "Another agent framework"
- "Graphs are the answer"

**Instead**:
- An engineering approach to hybrid systems — optimizing for **evolution**, not just power
- Architecture derived from two independent motivations (power and evolvability)
- Practical implementation that makes progressive stabilization cheap

---

## The Tradeoffs (Honest)

**Good fit**: prototyping with progressive stabilization, Python control flow, refactoring between LLM and code

**Poor fit**: durable workflows with checkpointing, distributed orchestration, graph-based visualization

**Current status**: Research-grade. The concepts are more mature than the implementation.

---

<!-- _class: title -->

## One Slide Summary

> "Two roads — power and evolvability — both need recursive dispatch. RLMs optimize for power. llm-do optimizes for evolution, making the engineering lifecycle work for hybrid systems."

> "Start stochastic for flexibility. Stabilize as patterns emerge. The unified interface makes this movement cheap."

---

## Resources

- **GitHub**: github.com/zby/llm-do
- **Theory**: `docs/theory.md` — stochastic computation model
- **Architecture**: `docs/architecture.md` — internal structure
- **Examples**: `examples/data_report*` — stabilization progression

**Questions?**

---

<!-- _class: title -->

# Backup Slides

---

## Backup: File Organizer Example

Alternative demo showing semantic/mechanical separation:

- LLM decides what files should be called *(semantic)*
- Python sanitizes filenames *(mechanical)*

---

## Backup: The Entry Point Patterns

Three orchestration styles:

1. **Agent entry** — LLM orchestrates
2. **Code entry** — Python orchestrates
3. **Orchestrating tool** — encapsulated workflow

---

## Backup: Comparison to LangGraph

| Aspect         | Graph DSLs              | llm-do                 |
|----------------|-------------------------|------------------------|
| Control flow   | Declarative (nodes/edges) | Imperative (Python)  |
| Refactoring    | Redraw the graph        | Change code            |
| Mental model   | Dataflow                | Function calls         |
| State          | Global context          | Local scope            |
