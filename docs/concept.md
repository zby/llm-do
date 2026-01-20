# llm-do: Concept and Design

> The way to build useful non-deterministic systems more complex than chat is to make them deterministic at key spots.

## The Hybrid VM

LLMs can be treated as interpreters. Give an LLM a sufficiently detailed spec, and it executes it—"simulation with sufficient fidelity is implementation." Projects like [OpenProse](https://github.com/openprose/prose) demonstrate this: a pure LLM VM where natural language specs become executable programs.

But pure LLM VMs have limitations:
- **Cost**: Every operation costs tokens
- **Latency**: Every step requires an API round-trip
- **Reliability**: Everything is stochastic

**llm-do is a hybrid VM.** It unifies LLM execution (neural) and Python execution (symbolic) under a single calling convention. Both are "operations" the VM can execute; callers don't know—or care—which is which.

```
Pure LLM VM:     Spec → LLM interprets → Output
Hybrid VM:       Spec → [LLM ⟷ Code ⟷ LLM ⟷ Code] → Output
```

The key insight: **the boundary between neural and symbolic is movable**. Start with LLM flexibility, stabilize to code as patterns emerge, soften back to LLM when edge cases multiply. The VM's unified calling convention makes this refactoring local—callers don't change.

## Why This Exists

LLM apps usually start as "just prompt it" and then hit a wall:

- **Pure prompts are flexible but fragile** — Hard to test, hard to debug, easy to regress.
- **Pure code is reliable but brittle** — Edge cases multiply into unmaintainable conditionals.
- **Graph/DSL frameworks add structure, but also new abstractions** — Refactoring means redrawing edges.

llm-do is a response: a hybrid VM that treats both LLM reasoning and Python code as first-class operations, letting you progressively move computation between them as your system evolves.

## Theoretical Foundation

LLMs are stochastic computers: specs map to distributions over behaviors, not deterministic outputs. Calls cross distribution boundaries between stochastic and deterministic execution. Reliability comes from shaping distributions and stabilizing boundaries where it matters.

See [LLM-Based Agentic Systems as Probabilistic Programs](theory.md) for the full treatment.

## Core Idea

**Workers are functions.**

A **worker** is a prompt + configuration + tools (and optionally schemas/policies), packaged as an executable unit. Workers call other workers and Python tools interchangeably—LLM reasoning and deterministic code interleave freely.

**Quick example**: A `file_organizer` worker renames files to consistent formats. Initially it decides naming conventions via LLM reasoning—flexible but slow. After observing patterns, you extract `sanitize_filename()` to Python: deterministic, tested, fast. The worker still handles ambiguous cases ("is this a date or a version number?"), but the common path is now code.

## Unified Function Space

Workers and tools share a calling convention. Whether a function is implemented as an LLM agent loop or Python code is an implementation detail. This is **neuro-symbolic computation** in practice:

```
LLM ──calls──▶ Tool ──calls──▶ LLM ──calls──▶ Tool ...
     reason         execute         reason
```

| Component | Strengths |
|-----------|-----------|
| Neural (LLM) | Flexible reasoning, handles ambiguity, contextual judgment |
| Symbolic (Tool) | Deterministic, precise, cheap, auditable |

This unification has a practical consequence for stabilization: when a worker graduates to a tool, callers don't change. Frameworks with separate calling mechanisms (e.g., `call_worker` vs `call_tool`) force caller updates on every stabilization—the calling convention fights the refactoring. Unified calling makes stabilization local.

The question isn't "LLM or code?" but **"how much of each, and where?"** Any component can slide along the spectrum as requirements evolve.

## Distribution Boundaries

Unified calling convention doesn't mean identical semantics. A call into an LLM crosses a distribution boundary:

|                  | Tool (deterministic) | Worker (stochastic) |
|------------------|----------------------|---------------------|
| Same input       | Same output          | Distribution over outputs |
| Failure modes    | Crashes, exceptions  | Hallucination, refusal, drift |
| Retry semantics  | Usually safe         | May get different result |
| Testing          | Assert equality      | Sample and check invariants |

The goal: an interface **thin enough to enable composition** and **honest enough that you know when you're crossing the boundary**.

See [theory.md](theory.md) for the formal treatment of distribution boundaries.

## The Harness Layer

On top of the VM sits a **harness**—the orchestration and control layer. Most agent frameworks are graph DSLs—nodes, edges, an engine. llm-do's harness is **imperative**:
- Your code owns control flow
- The harness intercepts at the tool layer (like syscalls)
- Call sites stay the same when implementations change

```python
# Today: LLM handles classification (neural operation)
result = await ctx.call("ticket_classifier", ticket_text)

# Tomorrow: stabilized to Python (symbolic operation, same call site)
result = await ctx.call("ticket_classifier", ticket_text)
```

The harness doesn't care whether it's dispatching to neural or symbolic—the VM abstraction handles that. Need a fixed sequence? Write a Python script. Need dynamic routing? Let the LLM decide. Same calling convention for both.

## Distribution Shaping in llm-do

Theory identifies what shapes distributions. Here's how those map to llm-do surfaces:

| Theory concept | llm-do surface |
|----------------|----------------|
| System prompt / examples | Worker `system_prompt`, `spec` fields |
| Tool definitions | Tool registry, `@tools.tool` decorators, schema validation |
| Output schemas | Structured outputs, Pydantic models, enums/ranges |
| Conversation history | Not reused yet; each run starts clean |
| Temperature / model | Worker config: `model`, `temperature`, defaults |

Each knob narrows the distribution differently. Schemas constrain structure; examples shift the mode; temperature controls sampling breadth.

## Tool Calls as Syscalls (Approvals)

Every tool call from an LLM can be intercepted for approval—at any nesting depth. Think of approvals as syscalls: when a worker needs to do something dangerous, execution blocks until the harness grants permission.

Pattern-based rules auto-approve safe operations; risky actions require consent. Progressive trust: start tight, loosen as confidence grows.

**Approvals reduce risk, not eliminate it.** Prompt injection can trick LLMs into misusing approved tools. Treat approvals as one defense layer, not a security boundary. For real isolation, use containers.

## Stabilizing and Softening Workflow

The unified interface enables refactoring in both directions.

### Stabilizing workflow

1. **Start stochastic** — Worker handles the task with LLM judgment
2. **Observe patterns** — Run tasks, watch what the LLM consistently does
3. **Extract to code** — Stable patterns become Python functions
4. **Keep stochastic edges** — Worker handles remaining ambiguous cases

**What changes when you stabilize:**
- Approvals: fewer needed (deterministic code is trusted)
- Tool surface: shrinks to what actually needs LLM judgment
- Testing: more surface area for traditional unit tests
- Performance: faster, cheaper, no API calls
- Auditability: deterministic paths are fully traceable

**Canonical example** — The pitchdeck progression:
- [`pitchdeck_eval`](../examples/pitchdeck_eval/) — All LLM: orchestrator decides everything
- [`pitchdeck_eval_stabilized`](../examples/pitchdeck_eval_stabilized/) — Extracted `list_pitchdecks()` to Python
- [`pitchdeck_eval_code_entry`](../examples/pitchdeck_eval_code_entry/) — Python orchestration, LLM only for analysis

### Softening workflow

**Extension** (common): Need new capability? Write a spec and plug it in:
```python
result = await ctx.call("sentiment_analyzer", customer_feedback)
```

**Replacement** (rare): Rigid code drowning in edge cases? Swap it for a worker that handles linguistic variation.

### Hybrid pattern

Python handles deterministic logic; workers handle judgment:

```python
@tools.tool
async def evaluate_document(ctx: RunContext[WorkerRuntime], path: str) -> dict:
    content = load_file(path)  # deterministic
    if not validate_format(content):
        raise ValueError("Invalid format")

    analysis = await ctx.deps.call("content_analyzer", {"input": content})  # stochastic

    return {"score": compute_score(analysis), "analysis": analysis}  # deterministic
```

Think "deterministic pipeline that uses LLM where judgment is needed."

## Versioning and Reproducibility

When you stabilize (one-shot or progressive), you create artifacts that should be versioned:
- Worker specs (the intent)
- Generated/stabilized code (the frozen sample)
- Model + decoding params when reproducibility matters

Don't rely on "re-generate later" as a build step—regeneration gives you a different sample. Treat worker specs and stabilized artifacts as deployable inputs.

## Testing Stance

**Stochastic components**: Run N times, assert invariants hold across samples. This is statistical testing, not equality assertions.

**Deterministic components**: Normal unit tests. Assert equality.

**Stabilizing increases testable surface**: Every piece you extract to Python becomes traditionally testable. This is a strong practical argument for progressive stabilizing.

See [architecture.md](architecture.md) for harness logging and approval mechanics.

## Tradeoffs

**llm-do is a good fit when you want:**
- Normal-code control flow (branching, loops, retries)
- Fast prototyping that can be progressively stabilized
- Tight scoping and tool-level auditability
- Flexibility to refactor between LLM and code

**It may be a poor fit if you need:**
- Durable workflow engine with checkpointing/replay
- Graph visualization as the primary interface
- Distributed orchestration out of the box

llm-do can be a component *within* durable workflow systems, but doesn't replace Temporal, Prefect, or similar engines.

## Design Principles

1. **Hybrid VM** — Neural and symbolic operations unified under one execution model
2. **Workers as functions** — Focused, composable units
3. **Unified calling convention** — Workers and tools call each other freely; callers don't know which is which
4. **Movable boundaries** — Stabilize to code as patterns emerge; soften back to LLM when needed
5. **Harness for control** — Imperative orchestration, syscall-style approvals
6. **Bounded recursion** — Depth limits prevent runaway recursion

---

**Further reading:**
- [theory.md](theory.md) — Probabilistic programs framing: distribution boundaries, stabilizing/softening, the harness pattern
- [architecture.md](architecture.md) — Internal structure: runtime scopes, execution flow, approval mechanics
- [reference.md](reference.md) — API reference: calling workers from Python, writing toolsets, worker file format
- [examples/](../examples/) — Working examples showing the stabilizing progression
