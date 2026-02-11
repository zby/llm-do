# LLM Day 2026 Warsaw - Presentation Plan v2

## One Interface: Fluid Movement Between LLM and Code

**Duration**: 30 minutes (25 content + 5 Q&A)

---

## Through-line

> "LLMs are probabilistic computers — prompts are how you program them. Real systems need both LLM and code, recursively interleaved. Two independent communities discovered this need. They diverge on design, but both require a calling convention at the boundary. llm-do chooses a unified interface — making the boundary invisible, so logic flows freely between LLM and code as systems evolve."

---

## Title Options

- **"One Interface: Fluid Movement Between LLM and Code"** (registered)
- "Two Roads to Recursive Dispatch: Power and Evolution in LLM-Code Systems"
- "Extend, Stabilize, Recurse: A Unified Interface for LLM and Code"

---

## Structure Overview

| Part | Topic | Time |
|------|-------|------|
| 1 | The Insight: Two Modes, Two Roads | 4 min |
| 2 | One Interface | 3 min |
| 3 | See It Work | 6 min |
| 4 | Fluid Movement | 3 min |
| 5 | Close | 3 min |
| | Q&A | 5 min |
| | **Total** | **24 min** |

---

## Part 1: The Insight (4 min)

### Slide 1: Title Slide

**"One Interface: Fluid Movement Between LLM and Code"**

Zbigniew Lukasiak
LLM Day 2026, Warsaw

---

### Slide 2: Prompts Are Like Code

You instruct, the machine executes.

- **Code**: you write precise instructions → computer executes deterministically
- **Prompts**: you describe intent → LLM executes stochastically

Both are ways of telling a computer what to do. One is precise, the other is flexible.

**So what**: "This isn't a metaphor. LLMs can be formally modelled as probabilistic computers — and prompts are the way to program them."

---

### Slide 3: The Hybrid Computer

Some tasks are better as prompts, some as code:

- **Code excels at**: deterministic logic, speed, precision, cost
- **Prompts excel at**: ambiguity, creativity, interpretation, flexibility

**Neither dominates.** You need both — and any real system uses both. This is **neuro-symbolic computing** — neural networks and traditional code, combined.

**So what**: "If neither mode is sufficient alone, the question becomes: how do you combine them?"

---

### Slide 4: Why Recursive?

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

### Slide 5: RLMs — The REPL

Recursive Language Models (Prime Intellect, Oct 2025) formalize this with an elegant approach: give the LLM a Python REPL.

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

**So what**: "RLMs made recursive dispatch rigorous — and the approach is elegantly simple because code is ephemeral."

---

### Slide 6: My Road — Evolution

> "I arrived at the same architecture independently — with a different priority."

**The goal**: Systems that grow and mature over time

> "Imagine a computer you extend by talking to it."

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

**The priority**: enabling the system to **evolve**. This is **llm-do**.

---

## Part 2: One Interface (3 min)

### Slide 7: The Key Differences

Same structural need — recursive dispatch. Different design choices.

| | RLM | llm-do |
|---|-----|--------|
| **Focus** | **Recursive dispatch** | **System evolution** |
| Code lifecycle | Ephemeral (generated, used, discarded) | Stored and evolved over time |
| Data passing | REPL variables (ephemeral) | Disk reads (natural for programmers) |
| User approvals | None (pure computation) | Full harness |
| Progressive stabilization | Not a goal | Core design driver |

**RLMs formalized recursive dispatch. llm-do adds the machinery for systems that mature over time.**

---

### Slide 8: llm-do's Design Choice

> "Whether a capability is neural (LLM) or symbolic (code) should be invisible at the call site."

This follows directly from the evolution priority. If your system is going to change over time — logic moving from LLM to code and back — the boundary must be cheap to cross.

This is an engineering choice, not a research choice. It enables:
- Refactoring without breaking callers
- Progressive stabilization as patterns emerge
- Experimentation: swap implementations freely

*(Pause. Let this land.)*

---

## Part 3: See It Work (6 min)

### Slide 9: llm-do in Practice — The Manifest

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

### Slide 10: llm-do in Practice — The Agent

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

### Slide 11: llm-do in Practice — Tools

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

### Slide 12: Data Report Generator — Setup

Two agents working together:

- **`main`** — the orchestrator: finds CSV files, calls the analyzer, writes reports
- **`analyze_dataset`** — does the analysis: reads data, computes stats, writes narrative

We'll show two versions:
1. **Prototype**: `analyze_dataset` is all-LLM — one prompt does everything
2. **Stabilized**: `analyze_dataset` becomes hybrid — code handles mechanical parts, LLM handles interpretation

**The key**: `main` never changes between versions. Same call, same interface.

---

### Slide 13: Version 1 — All LLM (Prototype)

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

### Slide 14: Version 1 — Prototype Running

Screenshot: `screenshot-prototype-tool-call.png`

Shows `main` calling `analyze_dataset`, which calls `read_file` to read raw CSV data. The LLM is doing all the work — reading, parsing, computing.

---

### Slide 15: The Approval Harness

Screenshot: `screenshot-approval.png`

Shows the approval prompt for `write_file` — the operator sees the full report and can approve or deny. This is the harness in action.

---

### Slide 16: Version 2 — Hybrid (Stabilized)

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

### Slide 17: Version 2 — Stabilized Running

Screenshot: `screenshot-stabilized-tool-call.png`

Shows `main` calling `analyze_dataset`, which calls only `write_narrative` — the code handled CSV reading, stats, and trend detection silently. Only the reasoning task reaches the LLM.

---

### Slide 18: Version 2 — Result

Screenshot: `screenshot-stabilized-tool-result.png`

Shows the final output: a formatted statistics table (produced by code — deterministic) followed by narrative interpretation (produced by LLM). The numbers are reliable; the narrative is creative.

---

## Part 4: Fluid Movement (3 min)

### Slide 19: Stabilizing and Softening

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
This is what "fluid movement" means — and the unified interface makes it cheap.

---

### Slide 20: What Changes When You Stabilize

| Aspect | Stochastic (LLM) | Stabilized (Code) |
|--------|------------------|-------------------|
| **Testing** | Sample N times, check invariants | Assert equality |
| **Performance** | API calls, seconds | Microseconds |
| **Cost** | Tokens per call | Zero marginal cost |
| **Auditability** | Opaque reasoning | Full trace |
| **Approvals** | May need human review | Trusted (your code) |

**So what**: "Every piece you stabilize becomes traditionally testable. Progressive stabilization = progressive confidence."

---

## Part 5: Close (3 min)

### Slide 21: The Tradeoffs (Honest)

**Good fit**: prototyping with progressive stabilization, Python control flow, refactoring between LLM and code

**Poor fit**: durable workflows with checkpointing, distributed orchestration, graph-based visualization

**Current status**: Research-grade. The concepts are more mature than the implementation.

---

### Slide 22: One Slide Summary

> "LLMs are probabilistic computers. Real systems need both LLM and code, recursively interleaved. llm-do provides one interface — making the boundary invisible, so logic flows freely between LLM and code as systems evolve."

---

### Slide 23: Resources

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
| 4 | Task decomposition tree | Static |
| 19 | Stabilize/Soften | Static with bidirectional arrows |

### "So What?" Moments

| After... | So what |
|----------|---------|
| Prompts are like code | "LLMs are probabilistic computers — prompts program them" |
| Hybrid computer | "Neither mode is sufficient — how do you combine them?" |
| Why recursive | "One layer of tools only reaches level 1 — full power requires arbitrary interleaving" |
| RLMs | "RLMs made recursive dispatch rigorous — elegantly simple because code is ephemeral" |
| My road | "Same architecture, different priority — evolution" |
| Key differences | "RLMs formalized recursive dispatch — llm-do adds machinery for evolution" |
| Design choice | "The unified boundary follows from the evolution priority" |
| Data report demo | "Same call, same name — the caller never knew it changed" |
| Fluid movement | "The system breathes — logic moves in both directions" |
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

### Backup 4: The Harness Pattern

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

## CFP Materials (Updated)

### Title

**"One Interface: Fluid Movement Between LLM and Code"**

### Elevator Pitch (300 chars)

> LLMs are probabilistic computers. Real systems need both LLM and code, recursively interleaved. llm-do provides one interface — making the boundary invisible, so logic flows freely between LLM and code as systems evolve from prototype to production.

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
