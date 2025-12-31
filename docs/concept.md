# llm-do: Concept and Design

> The way to build useful non-deterministic systems more complex than chat is to make them deterministic at key spots.

## Why This Exists

LLM apps usually start as "just prompt it" and then hit a wall:

- **Pure prompts are flexible but fragile** — Hard to test, hard to debug, easy to regress.
- **Pure code is reliable but brittle** — Edge cases multiply into unmaintainable conditionals.
- **Graph/DSL frameworks add structure, but also new abstractions** — Refactoring means redrawing edges.

llm-do is a response: treat prompts as callable units, let control flow live in code or LLM instructions (your choice), and progressively replace uncertainty with determinism where it pays off.

## Theoretical Foundation

LLMs are stochastic computers: specs map to distributions over behaviors, not deterministic outputs. Calls cross distribution boundaries between stochastic and deterministic execution. Reliability comes from shaping distributions and hardening boundaries where it matters.

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

## Harness, Not Graph

Most agent frameworks are graph DSLs—nodes, edges, an engine. llm-do is an **imperative harness**:
- Your code owns control flow
- llm-do intercepts at the tool layer
- Call sites stay the same when implementations change

```python
# Today: LLM handles classification
result = await ctx.call("ticket_classifier", ticket_text)

# Tomorrow: hardened to Python (same call site)
result = await ctx.call("ticket_classifier", ticket_text)
```

Need a fixed sequence? Write a Python script. Need dynamic routing? Let the LLM decide. Same semantics for both.

## Distribution Shaping in llm-do

Theory identifies what shapes distributions. Here's how those map to llm-do surfaces:

| Theory concept | llm-do surface |
|----------------|----------------|
| System prompt / examples | Worker `system_prompt`, `spec` fields |
| Tool definitions | Tool registry, `@tools.tool` decorators, schema validation |
| Output schemas | Structured outputs, Pydantic models, enums/ranges |
| Conversation history | Run context, delegation patterns, `ctx.call()` |
| Temperature / model | Worker config: `model`, `temperature`, defaults |

Each knob narrows the distribution differently. Schemas constrain structure; examples shift the mode; temperature controls sampling breadth.

## Tool Calls as Syscalls (Approvals)

Every tool call from an LLM can be intercepted for approval—at any nesting depth. Think of approvals as syscalls: when a worker needs to do something dangerous, execution blocks until the harness grants permission.

Pattern-based rules auto-approve safe operations; risky actions require consent. Progressive trust: start tight, loosen as confidence grows.

**Approvals reduce risk, not eliminate it.** Prompt injection can trick LLMs into misusing approved tools. Treat approvals as one defense layer, not a security boundary. For real isolation, use containers.

## Hardening and Softening Workflow

The unified interface enables refactoring in both directions.

### Hardening workflow

1. **Start stochastic** — Worker handles the task with LLM judgment
2. **Observe patterns** — Run tasks, watch what the LLM consistently does
3. **Extract to code** — Stable patterns become Python functions
4. **Keep stochastic edges** — Worker handles remaining ambiguous cases

**What changes when you harden:**
- Approvals: fewer needed (deterministic code is trusted)
- Tool surface: shrinks to what actually needs LLM judgment
- Testing: more surface area for traditional unit tests
- Performance: faster, cheaper, no API calls
- Auditability: deterministic paths are fully traceable

**Canonical example** — The pitchdeck progression:
- [`pitchdeck_eval`](../examples/pitchdeck_eval/) — All LLM: orchestrator decides everything
- [`pitchdeck_eval_hardened`](../examples/pitchdeck_eval_hardened/) — Extracted `list_pitchdecks()` to Python
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

When you harden (one-shot or progressive), you create artifacts that should be versioned:
- Worker specs (the intent)
- Generated/hardened code (the frozen sample)
- Model + decoding params when reproducibility matters

Don't rely on "re-generate later" as a build step—regeneration gives you a different sample. Treat worker specs and hardened artifacts as deployable inputs.

## Testing Stance

**Stochastic components**: Run N times, assert invariants hold across samples. This is statistical testing, not equality assertions.

**Deterministic components**: Normal unit tests. Assert equality.

**Hardening increases testable surface**: Every piece you extract to Python becomes traditionally testable. This is a strong practical argument for progressive hardening.

See [architecture.md](architecture.md) for harness logging and approval mechanics.

## Tradeoffs

**llm-do is a good fit when you want:**
- Normal-code control flow (branching, loops, retries)
- Fast prototyping that can be progressively hardened
- Tight scoping and tool-level auditability
- Flexibility to refactor between LLM and code

**It may be a poor fit if you need:**
- Durable workflow engine with checkpointing/replay
- Graph visualization as the primary interface
- Distributed orchestration out of the box

llm-do can be a component *within* durable workflow systems, but doesn't replace Temporal, Prefect, or similar engines.

## Design Principles

1. **Workers as functions** — Focused, composable units
2. **Unified function space** — Workers and tools call each other freely
3. **Honest abstraction** — Same calling convention, visible boundaries
4. **Bidirectional refactoring** — Harden as patterns stabilize; soften to add capabilities
5. **Guardrails by construction** — Schema validation and approval enforcement in code
6. **Bounded recursion** — Depth limits prevent runaway recursion

---

**Further reading:**
- [theory.md](theory.md) — Probabilistic programs framing: distribution boundaries, hardening/softening, the harness pattern
- [architecture.md](architecture.md) — Implementation details: worker definitions, toolsets, approvals, runtime API
- [examples/](../examples/) — Working examples showing the hardening progression
