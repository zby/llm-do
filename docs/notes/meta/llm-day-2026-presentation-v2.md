# LLM Day 2026 Warsaw - Presentation Plan v2

## Two Roads to the Hybrid VM

**Duration**: 30 minutes (25 content + 5 Q&A)

---

## Through-line

> "Two independent motivations—power and evolvability—both require recursive dispatch. RLMs optimize for power with an explicit boundary. llm-do optimizes for evolution with a unified calling convention, enabling systems that grow from prototype to production."

---

## Title Options

- "Two Roads to the Hybrid VM: Unifying LLM and Code"
- "Extend, Stabilize, Recurse: A Unified Interface for LLM and Code"
- "The Breathing System: Progressive Stabilization for LLM Applications"

---

## Structure Overview

| Part | Topic | Time |
|------|-------|------|
| 1 | The Vision: Extending Systems by Prompting | 4 min |
| 2 | Two Roads to the Same Design | 6 min |
| 3 | The Convergence: What Both Require | 3 min |
| 4 | The Concrete Refactoring Demo | 7 min |
| 5 | The Theoretical Frame | 5 min |
| 6 | Close & Takeaways | 3 min |
| | Q&A | 5 min |
| | **Total** | **33 min** |

---

## Part 1: The Vision (4 min)

### Slide 1: Title Slide

**"Two Roads to the Hybrid VM"**
*Unifying LLM and Code for Extensible, Powerful Systems*

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

## Part 4: The Concrete Refactoring Demo (7 min)

### Slide 11: Let's See It Work

**The pitchdeck evaluator progression**

Three versions of the same task, progressively stabilized:
1. All LLM (prototype)
2. Extracted tools (hybrid)
3. Code orchestration (production)

---

### Slide 12: Version 1 — Pure LLM

`examples/pitchdeck_eval/main.agent`

```
1. Use list_files("input", "*.pdf") to find all pitch deck PDFs.
2. For each PDF file:
   - Generate a file slug (lowercase, hyphenated, no extension)
   - Call pitch_evaluator(input=..., attachments=[...])
3. For each report returned:
   - Write it to evaluations/{file_slug}.md
```

**What the LLM is doing**:
- Finding files (mechanical)
- Generating slugs like `"aurora-solar.pdf" → "aurora-solar"` (mechanical)
- Orchestrating the loop (mechanical)
- Evaluating pitch decks (reasoning)

**Problem**: Tokens spent on slug generation. Behavior varies. This is purely mechanical—no reasoning needed.

---

### Slide 13: Version 2 — Extract the Mechanical

`examples/pitchdeck_eval_stabilized/tools.py`

```python
def list_pitchdecks(path: str = "input") -> list[dict]:
    """List pitch deck PDFs with pre-computed slugs."""
    result = []
    base = PROJECT_ROOT / path
    for pdf in sorted(base.glob("*.pdf")):
        slug = slugify(pdf.stem)  # Deterministic!
        result.append({
            "file": str(pdf.relative_to(PROJECT_ROOT)),
            "slug": slug,
            "output_path": f"evaluations/{slug}.md",
        })
    return result
```

Updated prompt (`main.agent`):

```
1. Call list_pitchdecks() to get all pitch decks.
2. For each item:
   - Call pitch_evaluator(...)
   - Write to item.output_path
```

**Key observation**: The LLM calls `list_pitchdecks()` exactly like it would call an agent. **Same calling convention.**

---

### Slide 14: Version 3 — Code Orchestration

`examples/pitchdeck_eval_code_entry/tools.py`

```python
async def main(_input_data, runtime: CallContext) -> str:
    decks = list_pitchdecks()           # Python (deterministic)

    for deck in decks:                   # Python loop (deterministic)
        report = await runtime.call_agent(
            "pitch_evaluator",           # LLM call (reasoning)
            {"input": "Evaluate this pitch deck.",
             "attachments": [deck["file"]]}
        )
        Path(deck["output_path"]).write_text(report)  # Python

    return f"Evaluated {len(decks)} pitch deck(s)"
```

**Now**: Python handles everything mechanical. LLM only does evaluation (actual reasoning).

---

### Slide 15: The Stabilization Spectrum

```
Original             Stabilized           Code Entry
────────────────────────────────────────────────────────
LLM lists files  →   Python tool      →   Python tool
LLM generates slugs → Python tool      →   Python tool
LLM orchestrates →   LLM orchestrates →   Python code
LLM evaluates    →   LLM evaluates    →   LLM evaluates
────────────────────────────────────────────────────────
     All LLM              Hybrid            Minimal LLM
```

**What changed**:
- Fewer tokens (no slug generation, no orchestration tokens)
- Faster (Python loops are microseconds)
- Deterministic file handling
- LLM focused on what it's good at: reasoning

**What stayed the same**: The call to `pitch_evaluator`. Same interface throughout.

---

### Slide 16: The Refactoring That Didn't Break

Imagine a **Version 4**: stabilize `pitch_evaluator` itself.

**Before** — `pitch_evaluator.agent` (LLM does everything):
```
# main.agent — the call site
Call pitch_evaluator(input="Evaluate this pitch deck.",
                     attachments=["input/aurora-solar.pdf"])
```
→ LLM reads PDF, scores dimensions, writes report (all neural)

**After** — `pitch_evaluator` becomes code wrapping an LLM:
```python
# tools.py — pitch_evaluator is now a Python function
async def pitch_evaluator(ctx, input: str, attachments: list[str]) -> str:
    pdf_path = validate_pdf(attachments[0])         # Code (deterministic)
    raw = await ctx.deps.call_agent(                # LLM (reasoning)
        "raw_evaluator",
        {"input": input, "attachments": [pdf_path]}
    )
    return enforce_report_format(raw)               # Code (deterministic)
```

**The call in `main.agent` doesn't change at all.**

First the LLM called another LLM. Now it calls code that calls an LLM. Same name, same arguments, same result. The caller never knew the difference.

*(This is also the `orchestrating_tool/deep_research` pattern — Python code orchestrating 3 agents, but the caller just sees `deep_research(question)`.)*

---

## Part 5: The Theoretical Frame (5 min)

### Slide 17: Why This Works — Distribution Boundaries

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

### Slide 18: Stabilizing and Softening

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

### Slide 19: What Changes When You Stabilize

| Aspect | Stochastic (LLM) | Stabilized (Code) |
|--------|------------------|-------------------|
| **Testing** | Sample N times, check invariants | Assert equality |
| **Performance** | API calls, seconds | Microseconds |
| **Cost** | Tokens per call | Zero marginal cost |
| **Auditability** | Opaque reasoning | Full trace |
| **Approvals** | May need human review | Trusted (your code) |

**So what**: "Every piece you stabilize becomes traditionally testable. Progressive stabilization = progressive confidence."

---

### Slide 20: The Harness Pattern

llm-do adds a harness on top of the hybrid VM:

- **Your code owns control flow** (or LLM does—your choice)
- **Tool calls intercepted** like syscalls
- **Approvals** block until permission granted
- **Observability** via message history, usage tracking

```
Agent/Code ──→ Harness ──→ Tool execution
                  │
           (approval check)
           (logging)
           (validation)
```

**Call sites stay stable. Implementations move across the boundary.**

---

## Part 6: Close (3 min)

### Slide 21: The Recipe

1. **Unify the calling convention** — LLM and code share the same interface
2. **Enable recursive dispatch** — neural and symbolic can call each other at any depth
3. **Stabilize progressively** — start stochastic, extract determinism as patterns emerge
4. **Keep the boundary visible** — that's where you refactor, test, and intervene

---

### Slide 22: What Makes This Different

**Not**:
- "How to prompt better"
- "Another agent framework"
- "Graphs are the answer"

**Instead**:
- An engineering approach to hybrid systems — optimizing for evolution, not just power
- Architecture derived from two independent motivations (power and evolvability)
- Practical implementation that makes progressive stabilization cheap

---

### Slide 23: The Tradeoffs (Honest)

**llm-do is a good fit when**:
- You're prototyping and will stabilize as patterns emerge
- You want Python control flow (not graph DSLs)
- You need tool-level auditability and approvals
- You expect to refactor between LLM and code

**It may be a poor fit when**:
- You need durable workflows with checkpointing/replay
- Graph visualization is your primary interface
- You need distributed orchestration out of the box

**Current status**:
- The API is unstable—expect breaking changes
- This is research-grade software, not production-hardened
- The concepts are more mature than the implementation

---

### Slide 24: One Slide Summary

> "Two roads—power and evolvability—both need recursive dispatch. RLMs optimize for power. llm-do optimizes for evolution, making the engineering lifecycle work for hybrid systems."

> "Start stochastic for flexibility. Stabilize as patterns emerge. The unified interface makes this movement cheap."

---

### Slide 25: Resources

- **GitHub**: github.com/zby/llm-do
- **Theory**: `docs/theory.md` — stochastic computation model
- **Architecture**: `docs/architecture.md` — internal structure
- **Examples**: `examples/pitchdeck_eval*` — stabilization progression

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
| 15 | Stabilization spectrum | Static table, highlight progression |
| 17 | Distribution boundaries | Progressive (LLM → tool → LLM) |
| 18 | Stabilize/Soften | Static with bidirectional arrows |

### "So What?" Moments

| After... | So what |
|----------|---------|
| The dream | "This is how software should grow" |
| Two roads | "Same need, different values — power vs. evolution" |
| Convergence | "The unified boundary follows from the evolution priority" |
| Refactoring demo | "Same interface throughout—refactoring was trivial" |
| Stabilization table | "Progressive stabilization = progressive confidence" |

### Demo Option

If live demo is possible:
1. Run `pitchdeck_eval` — show token usage
2. Run `pitchdeck_eval_stabilized` — show reduced tokens
3. Run `pitchdeck_eval_code_entry` — show only evaluation uses LLM

The numbers tell the story better than slides.

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

**"Two Roads to the Hybrid VM: Unifying LLM and Code"**

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
