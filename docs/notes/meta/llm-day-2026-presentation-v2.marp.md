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

**Zbigniew Łukasiak**
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

**The priority**: enabling the system to **evolve**. Evolution means refactoring must be cheap. This is **llm-do**.

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

**RLMs are elegantly simple. llm-do trades that simplicity for evolvability and practical completeness.**

---

## llm-do's Design Choices

Three engineering choices that add complexity:

1. **Unified calling convention** — LLM or code is invisible at the call site. Follows from evolvability: refactoring across the boundary changes nothing for callers.

2. **Stateful tools** — database connections, file handles, full lifecycle. Makes reentrancy hard, but covers real-world cases.

3. **Approval harness** — every tool call can be gated. Agents do real work (file writes, API calls), so you need consent.

Each makes the architecture harder. Each is necessary for a practical system — not a toy.

---

## llm-do Projects

A **project** is the analog of a program. Its elements:

- **Agents** (`.agent` files) — prompts with toolset declarations. Analog of functions.
- **Tools** (`.py` files) — Python code, also organized into toolsets.
- **Manifest** (`project.json`) — declares the elements, entry point, runtime config.

The same system can also be built entirely in Python code — but we haven't optimized that path yet. The declarative form makes it easier to inspect what the system can do.

---

## llm-do in Practice — The Manifest

**Prototype manifest** (`examples/data_report/project.json`):
```json
{
  "version": 1,
  "runtime": { "max_depth": 3 },
  "entry": {
    "agent": "main",
    "args": {
      "input": "Analyze all CSV datasets in the input directory"
    }
  },
  "agent_files": ["main.agent", "analyze_dataset.agent"],
  "python_files": ["schemas.py"]
}
```

In `examples/data_report_stabilized/project.json`, the flow is the same, but files switch to
`write_narrative.agent` and `tools.py`.

---

## llm-do in Practice — The Agent

**Prototype orchestrator** (`examples/data_report/main.agent`):
```yaml
---
name: main
description: Generate analysis reports for all CSV datasets.
toolsets:
  - analyze_dataset
  - filesystem_project
---

You generate analysis reports for CSV datasets.

1. Use `list_files("input", "*.csv")` to find all CSV files.
2. For each CSV file, call `analyze_dataset(path=<csv_path>)` to get the report
   and write it to `reports/<name>.md` using `write_file()`.
```

An agent is a prompt with toolset declarations. Toolsets are loaded by name — they can be LLM agents or code tools.

---

## Data Report Generator — Setup

Two versions of the same workflow:

- **Prototype (`examples/data_report`)**:
  - `main` (agent orchestrator)
  - `analyze_dataset` (LLM agent)
- **Stabilized (`examples/data_report_stabilized`)**:
  - `main` (agent orchestrator)
  - `analyze_dataset` (Python tool in `report_tools`)
  - `write_narrative` (LLM agent)

We'll show two versions:
1. **Prototype**: `analyze_dataset` is all-LLM — one prompt does everything
2. **Stabilized**: `analyze_dataset` becomes hybrid — code handles mechanical parts, LLM handles interpretation

**The key**: the workflow call stays `analyze_dataset(path=<csv_path>)`.
The implementation moves from LLM agent to Python tool + sub-agent.

---

## Version 1 — All LLM (Prototype)

`examples/data_report/analyze_dataset.agent`:
```yaml
---
name: analyze_dataset
description: Analyze a CSV dataset and produce a narrative report.
input_model_ref: schemas.py:DatasetInput
toolsets:
  - filesystem_project
---

You are a data analyst. You will receive a path to a CSV file.

1. Read the CSV file using `read_file(path)`.
2. Compute summary statistics (mean, median, min, max) for numeric columns.
3. Identify notable trends and outliers.
4. Write a narrative markdown report with statistics, interpretation,
   and recommendations.
```

---

## Version 1 — The Problem

**What the LLM is doing**:
- Reading and parsing CSV *(mechanical)*
- Computing statistics *(mechanical)*
- Identifying trends *(reasoning)*
- Writing narrative *(reasoning)*

**Problem**: LLM computes averages — expensive, sometimes wrong. This is calculator work.

---

## Version 1 — Prototype Running

![w:1100](screenshot-prototype-tool-call.png)

<!--
Prototype execution trace. The main agent (depth 1) calls list_files to find CSVs, then calls analyze_dataset. Since analyze_dataset is an LLM agent, it runs at depth 2 and calls read_file itself to read the raw CSV data. The LLM is doing everything — parsing, statistics, interpretation.
-->

---

## Version 1 — Prototype Result

![w:1100](screenshot-prototype-result.png)

<!--
The all-LLM result: a long narrative with statistics, trends, and recommendations. The LLM computed all the numbers itself — expensive and potentially inaccurate. This is the motivation for stabilization.
-->

---

## The Approval Harness

![w:1100](screenshot-approval.png)

<!--
The approval dialog for write_file. The agent wants to write the report to disk — a side effect. The harness intercepts the call and shows the full content for review. Options: Approve, Approve for session, Deny, Quit. This is the trust boundary — every side-effectful tool call goes through it.
-->

---

## Version 2 — Hybrid (Stabilized)

`examples/data_report_stabilized/tools.py`:
```python
@tools.tool
async def analyze_dataset(ctx, path: str) -> str:
    full_path = PROJECT_ROOT / path
    rows = list(csv.DictReader(open(full_path)))  # Code (mechanical)
    stats = _compute_summary(rows)                 # Code (mechanical)
    trends = _detect_trends(rows)                  # Code (mechanical)

    runtime = ctx.deps                             # LLM (reasoning)
    narrative = await runtime.call_agent(
        "write_narrative",
        {"input": f"Stats: {stats}\nTrends: {trends}"},
    )
    return narrative
```

**Same call. Same name. Same arguments.** The caller never knew it changed.
Code handles what's mechanical. LLM handles what needs interpretation.

---

## Version 2 — Stabilized Running

![w:1100](screenshot-stabilized-tool-call.png)

<!--
Stabilized execution trace. The main agent calls list_files and then analyze_dataset — same as before. But now analyze_dataset is a Python tool, not an LLM agent. Notice there's NO read_file call at depth 2 — the code reads the CSV directly. The only LLM call inside is write_narrative for interpretation.
-->

---

## Version 2 — Result

![w:1100](screenshot-stabilized-tool-result.png)

<!--
The stabilized result. The narrative is focused on interpretation because the mechanical work (parsing, statistics, trends) was done by code. Compare with the prototype result — same quality narrative, but statistics are computed deterministically.
-->

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

| Aspect           | LLM (stochastic)                 | Extracted to code              |
|------------------|-----------------------------------|---------------------------------|
| **Testing**      | Sample N times, check invariants  | Assert equality                |
| **Performance**  | API call + token generation       | No API call                    |
| **Cost**         | Tokens per call                   | No token cost                  |
| **Auditability** | Opaque reasoning                  | Full trace                     |
| **Approvals**    | May need human review             | Can be pre-approved by policy  |

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

> "Real systems need both LLM and code, recursively interleaved. llm-do provides one interface — making the boundary invisible — with the engineering needed for a practical, evolving system: stateful tools, approvals, and progressive stabilization."

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

---

## Backup: Approvals — Work in Progress

**Already working**: tools declare fine-grained approval requirements, agents declare which toolsets they use, every call goes through the harness. This is already far beyond RLMs, which have no approval model at all.

**Current limitation**: the reconciliation is coarse — the manifest sets one global `approval_mode`. Agent permissions and tool requirements aren't yet matched at a granular level.

**Next step**: a **capabilities-based** design — agents granted specific capabilities, tools requiring specific capabilities. An improvement, not a redesign.
