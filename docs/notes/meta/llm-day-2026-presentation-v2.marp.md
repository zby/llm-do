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

# One Interface: Fluid Movement Between LLM and Code

**Zbigniew Lukasiak**
LLM Day 2026, Warsaw

---

## Prompts Are Like Code

You instruct, the machine executes.

- **Code**: you write precise instructions &rarr; computer executes deterministically
- **Prompts**: you describe intent &rarr; LLM executes stochastically

Both are ways of telling a computer what to do. One is precise, the other is flexible.

**This isn't a metaphor. LLMs can be formally modelled as probabilistic computers — and prompts are the way to program them.**

---

## The Hybrid Computer

Some tasks are better as prompts, some as code:

- **Code excels at**: deterministic logic, speed, precision, cost
- **Prompts excel at**: ambiguity, creativity, interpretation, flexibility

**Neither dominates.** You need both — and any real system uses both. This is **neuro-symbolic computing** — neural networks and traditional code, combined.

**If neither mode is sufficient alone, the question becomes: how do you combine them?**

---

## Why Recursive?

The standard agent loop is flat — LLM and tools alternate, but tools are always leaves:

```
LLM → tool → LLM → tool → LLM → done
```

But real tasks decompose fractally — a tool itself may need judgment, which needs another tool:

```
LLM decides what to analyze          (judgment)
  └─ Code reads and parses data      (mechanical)
       └─ LLM interprets anomalies   (judgment)
            └─ Code looks up history  (mechanical)
                 └─ LLM writes report (judgment)
```

**One layer of "LLM calls tools" only reaches level 1. Full power requires arbitrary interleaving.**

---

## RLMs — The REPL

**Recursive Language Models** (Prime Intellect, Oct 2025) formalize this with an elegant approach: give the LLM a Python REPL.

```
Task (ambiguous → LLM)
├── Subtask A (mechanical → code)
├── Subtask B (judgment → LLM)
│   ├── Sub-B1 (lookup → code)
│   └── Sub-B2 (creative → LLM)
└── Subtask C (formatting → code)
```

The LLM writes code, the REPL executes it. Code orchestrates sub-agents (map-reduce), accumulating partial results in REPL variables — keeping data out of the LLM's context window.

The approach is elegantly simple: code is ephemeral and sandboxed, so there's no need to store code, manage approvals, or handle reentrant state.

---

## My Road — Evolution

> "I arrived at the same architecture independently — with a different priority."

**The goal**: Systems that grow and mature over time

> "Imagine a computer you extend by talking to it."

```
User describes intent → LLM performs it → Save as named capability
→ Observe patterns → Encode stable parts as code → Hybrid capability
```

**The priority**: enabling the system to **evolve**. This is **llm-do**.

---

## The Key Differences

Same structural need — recursive dispatch. Different design choices.

|                            | RLM               | llm-do                      |
|----------------------------|--------------------|-----------------------------|
| **Focus**                  | **Recursive dispatch** | **System evolution**    |
| Code lifecycle             | Ephemeral          | Stored and evolved          |
| Data passing               | REPL variables     | Disk reads                  |
| User approvals             | None (sandboxed)   | Full harness                |
| Progressive stabilization  | Not a goal         | Core design driver          |

**RLMs formalized recursive dispatch. llm-do adds the machinery for systems that mature over time.**

---

## llm-do's Design Choice

> "Whether a capability is neural (LLM) or symbolic (code) should be invisible at the call site."

This follows directly from the evolution priority. If your system is going to change over time — logic moving from LLM to code and back — the boundary must be cheap to cross.

This is an **engineering choice**, not a research choice. It enables:

- Refactoring without breaking callers
- Progressive stabilization as patterns emerge
- Experimentation: swap implementations freely

<!-- Pause. Let this land. This is the core design thesis. -->

---

## llm-do in Practice — The Manifest

**The manifest** (`project.json`):
```json
{
  "runtime": { "approval_mode": "approve_all", "max_depth": 5 },
  "entry": { "agent": "main" },
  "agent_files": ["main.agent"],
  "python_files": ["tools.py"]
}
```

The manifest declares what files make up the project, which agent to start with, and runtime config (approval mode, max recursion depth).

---

## llm-do in Practice — The Agent

**The agent** (`main.agent`):
```yaml
---
name: main
toolsets:
  - data_tools
---
You are a data processor.
Use tools for all data formatting and statistics.
```

An agent is a prompt with toolset declarations. Toolsets are loaded by name — they can be LLM agents or code tools.

---

## llm-do in Practice — Tools

**Tools** (`tools.py`):
```python
@data_tools.tool
def calculate_stats(numbers: str) -> str:
    """Calculate basic statistics."""
    nums = [float(x) for x in numbers.split(",")]
    return f"count={len(nums)}, avg={sum(nums)/len(nums):.2f}"

@data_tools.tool
def send_notification(message: str, channel: str = "default") -> str:
    """Send a notification message."""
    return f"Notification sent to {channel}: {message}"
```

Every tool call goes through the approval harness. The manifest's `approval_mode` controls whether the operator is prompted.

---

## Data Report Generator — Setup

Two agents working together:

- **`main`** — the orchestrator: finds CSV files, calls the analyzer, writes reports
- **`analyze_dataset`** — does the analysis: reads data, computes stats, writes narrative

We'll show two versions:
1. **Prototype**: `analyze_dataset` is all-LLM — one prompt does everything
2. **Stabilized**: `analyze_dataset` becomes hybrid — code handles mechanical parts, LLM handles interpretation

**The key**: `main` never changes between versions. Same call, same interface.

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

## Version 1 — Prototype Running

![w:1100](screenshot-prototype-tool-call.png)

---

## The Approval Harness

![w:1100](screenshot-approval.png)

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

## Version 2 — Stabilized Running

![w:1100](screenshot-stabilized-tool-call.png)

---

## Version 2 — Result

![w:1100](screenshot-stabilized-tool-result.png)

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

**The system breathes.** This is what "fluid movement" means — and the unified interface makes it cheap.

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

## The Tradeoffs (Honest)

**Good fit**: prototyping with progressive stabilization, Python control flow, refactoring between LLM and code

**Poor fit**: durable workflows with checkpointing, distributed orchestration, graph-based visualization

**Current status**: Research-grade. The concepts are more mature than the implementation.

---

<!-- _class: title -->

## One Slide Summary

> "LLMs are probabilistic computers. Real systems need both LLM and code, recursively interleaved. llm-do provides one interface — making the boundary invisible, so logic flows freely between LLM and code as systems evolve."

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

---

## Backup: The Harness Pattern

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
