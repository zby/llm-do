# LLM Day 2026 Warsaw - Presentation Plan v2

## Three Roads to the Hybrid VM

**Duration**: 30 minutes (25 content + 5 Q&A)

---

## Through-line

> "Three independent motivations—extensibility, computational power, and neuro-symbolic completeness—all converge on the same architecture: a unified calling convention enabling recursive dispatch across the neural-symbolic boundary."

---

## Title Options

- "Three Roads to the Hybrid VM: Unifying LLM and Code"
- "Extend, Stabilize, Recurse: A Unified Interface for LLM and Code"
- "The Breathing System: Progressive Stabilization for LLM Applications"

---

## Structure Overview

| Part | Topic | Time |
|------|-------|------|
| 1 | The Vision: Extending Systems by Prompting | 4 min |
| 2 | Three Roads to the Same Design | 6 min |
| 3 | The Convergence: What All Three Require | 3 min |
| 4 | The Concrete Refactoring Demo | 7 min |
| 5 | The Theoretical Frame | 5 min |
| 6 | Close & Takeaways | 3 min |
| | Q&A | 5 min |
| | **Total** | **33 min** |

---

## Part 1: The Vision (4 min)

### Slide 1: Title Slide

**"Three Roads to the Hybrid VM"**
*Unifying LLM and Code for Extensible, Powerful, Complete Systems*

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

## Part 2: Three Roads (6 min)

### Slide 4: "I Wasn't Alone"

> "When I started thinking about what this system needs, I found others arriving at the same place from different directions."

Three independent motivations, one architecture.

---

### Slide 5: Road 1 — Extensibility (My Origin)

**The goal**: Systems that grow by prompting

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

**What this requires**:
- Save prompts as callable units
- Unified interface (prompts and code look the same)
- Progressive stabilization (move logic prompt → code)

---

### Slide 6: Road 2 — Computational Power (RLM Perspective)

**The goal**: Maximum expressive power

- Code: deterministic, fast, cheap—but rigid
- Prompts: flexible, handle ambiguity—but expensive, variable
- **Neither dominates**—each is better for different subtasks

**The recursive insight**:

```
Task (ambiguous → LLM)
├── Subtask A (mechanical → code)
├── Subtask B (judgment → LLM)
│   ├── Sub-B1 (lookup → code)
│   └── Sub-B2 (creative → LLM)
└── Subtask C (formatting → code)
```

At any depth, choose the best execution mode for that subtask.

**What this requires**:
- Recursive dispatch between LLM and code
- Mode choice independent of nesting depth
- Unified calling convention

---

### Slide 7: Road 3 — Neuro-Symbolic Completeness

**The goal**: Full neuro-symbolic power

Current tool-use is shallow:
```
LLM → tool → result → LLM
```

The tool can't use LLM reasoning. Symbolic layer is "leaves only."

**Full power requires**:
```
LLM → code → LLM → code → LLM → ...
```

- Symbolic components that invoke neural components
- Neural components that invoke symbolic components
- Arbitrary nesting depth

**This is just recursion across the neural-symbolic boundary.**

---

### Slide 8: The Convergence Diagram

```
     EXTENSIBILITY           POWER            COMPLETENESS
           │                   │                    │
    "save prompts        "use the best        "neural and symbolic
     as extensions"       tool for each         should interleave
                          subtask"              at any depth"
           │                   │                    │
           └───────────────────┼────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  UNIFIED CALLING    │
                    │    CONVENTION       │
                    └─────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  RECURSIVE DISPATCH │
                    └─────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    PROGRESSIVE      │
                    │   STABILIZATION     │
                    └─────────────────────┘
```

*(Build this progressively: show three roads, then convergence)*

---

## Part 3: The Convergence (3 min)

### Slide 9: What All Three Require

| Requirement | Extensibility | Power | Completeness |
|-------------|---------------|-------|--------------|
| **Unified calling** | Prompts & code interchangeable | Subtasks route freely | Neural/symbolic interleave |
| **Recursive dispatch** | Call saved prompts from code | Decompose at any depth | Full expressiveness |
| **Progressive refinement** | Stabilize as patterns emerge | Optimize each subtask | Balance flexibility/efficiency |

**The claim**: These aren't independent features. They're consequences of taking any of these motivations seriously.

**So what**: "The convergence is evidence the design is sound."

---

### Slide 10: The One-Line Insight

> "Whether a capability is neural (LLM) or symbolic (code) should be invisible at the call site."

This single constraint enables:
- Refactoring without breaking callers
- Recursive composition at any depth
- Progressive stabilization as patterns emerge

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
    for pdf in sorted(base.glob("*.pdf")):
        slug = slugify(pdf.stem)  # Deterministic!
        result.append({
            "file": rel_path,
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

```python
# In pure LLM version (main.agent calls this)
await call("pitch_evaluator", {...})

# In stabilized version (main.agent still calls this)
await call("pitch_evaluator", {...})

# In code entry version (Python calls this)
await runtime.call_agent("pitch_evaluator", {...})
```

**Same name. Same interface. Different orchestration.**

The unified calling convention made this refactoring trivial.

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
- A coherent model for building reliable systems on stochastic foundations
- Architecture derived from three independent motivations
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

---

### Slide 24: One Slide Summary

> "Three roads—extensibility, power, completeness—converge on one architecture: unified calling convention, recursive dispatch, progressive stabilization."

> "Start stochastic for flexibility. Stabilize as patterns emerge. The unified interface makes this movement natural."

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
| 8 | Convergence | Progressive (three roads → requirements → conclusion) |
| 15 | Stabilization spectrum | Static table, highlight progression |
| 17 | Distribution boundaries | Progressive (LLM → tool → LLM) |
| 18 | Stabilize/Soften | Static with bidirectional arrows |

### "So What?" Moments

| After... | So what |
|----------|---------|
| The dream | "This is how software should grow" |
| Convergence | "Evidence the design is sound" |
| One-line insight | "This single constraint enables everything" |
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

**"Three Roads to the Hybrid VM: Unifying LLM and Code"**

### Elevator Pitch (300 chars)

> Extensibility, power, and neuro-symbolic completeness all require the same thing: unified calling between LLM and code. llm-do provides this, enabling systems that grow by prompting and stabilize to code as patterns emerge.

### Description

> This talk presents a unified architecture for LLM-based systems, derived from three independent motivations that converge on the same design requirements.
>
> First, the dream of extensible systems—computers you extend by talking to them, saving prompts as capabilities, and progressively stabilizing to code. Second, the power argument—at any level of task decomposition, you should use whichever execution mode (LLM or code) is best for that subtask. Third, neuro-symbolic completeness—full expressiveness requires recursive interleaving of neural and symbolic computation.
>
> All three require the same architecture: unified calling convention, recursive dispatch, and progressive stabilization. We demonstrate this with llm-do, showing concrete refactoring from all-LLM prototypes to production-ready hybrid systems—without changing call sites.
>
> Attendees will leave with a coherent model for building reliable systems on stochastic foundations, and practical patterns for organic system evolution from prototype to production.

### Bio

> Zbigniew Lukasiak has been building software since the dot-com era. He's worked across startups, large corporations, and academia—including the University of London, where he helped build PhilPapers, a comprehensive index of philosophy research used by academics worldwide.
>
> Having witnessed the birth of the web, he sees the same energy in LLMs today—and the same need for architectural discipline. He's the author of llm-do, an open-source hybrid VM for LLM applications that enables progressive stabilization from prototype to production.
