# llm-do: Concept and Design

> The way to build useful non-deterministic systems more complex than chat is to make them deterministic at key spots.

## Why This Exists

LLM apps usually start as "just prompt it" and then hit a wall:

- **Pure prompts are flexible but fragile** — Hard to test, hard to debug, easy to regress. As capabilities grow, the prompt becomes unmaintainable.

- **Pure code is reliable but brittle** — You end up writing heuristics where you actually need judgment. Edge cases multiply into unmaintainable conditionals.

- **Graph/DSL frameworks add structure, but also new abstractions** — Orchestration logic moves into a separate language/runtime. Refactoring means redrawing edges. The abstraction fights you when requirements change.

llm-do is a response: keep control flow in normal code, treat prompts as callable units, and progressively replace uncertainty with determinism where it pays off.

## Theoretical Foundation

llm-do is grounded in a view of LLMs as **stochastic computers**—systems that map natural language specifications to probability distributions over behaviors, rather than deterministic outputs. This model explains:

- Why prompts are powerful but fragile (they shape distributions, not exact behaviors)
- Why hardening matters (collapsing distributions toward determinism where reliability is needed)
- Why bidirectional refactoring is essential (logic needs to move fluidly across the stochastic/deterministic boundary)
- Why both specs and generated code must be versioned (stochastic compilation produces non-reproducible intermediate forms)

See [Stochastic Computation Theory: A Sketch](theory.md) for the full treatment.

## Core Idea

**Workers are functions.**

A **worker** is a prompt + configuration + tools (and optionally schemas/policies), packaged as an executable unit. Workers call other workers and Python tools interchangeably—LLM reasoning and deterministic code interleave freely.

**Quick example**: A `file_organizer` worker renames files to consistent formats. Initially it decides naming conventions via LLM reasoning—flexible but slow. After observing patterns, you extract `sanitize_filename()` to Python: deterministic, tested, fast. The worker still handles ambiguous cases ("is this a date or a version number?"), but the common path is now code. Approvals gate the actual `mv` operations throughout.

## Unified Function Space

Workers and tools are the same abstraction: **a callable**. Both can call each other in any combination—just like in a regular program. Whether a function is implemented as an LLM agent loop or Python code is an implementation detail; the calling convention is the same.

This is neuro-symbolic computing in practice:

```
LLM ──calls──▶ Tool ──calls──▶ LLM ──calls──▶ Tool ...
     reason         execute         reason
     decide         compute         decide
```

Each component plays to its strengths:

| Component | Strengths |
|-----------|-----------|
| Neural (LLM) | Flexible reasoning, handles ambiguity, contextual judgment |
| Symbolic (Tool) | Deterministic, precise, cheap, auditable |

The question isn't "LLM or code?" but **"how much of each, and where?"**

```
Pure Python ◄───────────────────────────────────────────► Pure Worker
(all symbolic)                                            (all neural)
      │                        │                               │
 compute_hash           smart_refactor                  code_reviewer
                    (deterministic flow,
                     calls LLM when stuck)
```

Any component can slide along this spectrum as requirements evolve.

## Unified but Not Uniform

The unified calling convention enables composition and refactoring—you can swap a worker for a tool or vice versa. But unification at the interface level doesn't mean identical semantics underneath.

A call into an LLM crosses a **distribution boundary**: from deterministic execution into stochastic computation and back. This matters:

|                  | Deterministic call (tool) | Stochastic call (worker) |
|------------------|---------------------------|--------------------------|
| Same input       | Same output               | Distribution over outputs |
| Failure modes    | Crashes, exceptions       | Hallucination, refusal, drift |
| Retry semantics  | Usually safe              | May get different result |
| Testing          | Assert equality           | Sample and check distribution |
| Debugging        | Trace execution           | Reshape probability distribution |

If the abstraction hides this boundary completely, you'll write code assuming reproducibility and get bitten. If the abstraction makes everything special-cased, you can't refactor.

The goal is an interface that's **thin enough to enable composition** and **honest enough that you know when you're crossing the boundary**. Same calling convention, different expectations.

## Harness, Not Graph

Most agent frameworks are **graph DSLs**—you define nodes and edges (DAGs, state machines, YAML orchestration), and an engine runs the graph.

llm-do is an **imperative harness**:
- Your code owns control flow
- llm-do intercepts at the **tool layer**

Need a fixed sequence? Write a Python script that calls workers.
Need dynamic routing? Let the LLM decide which worker to call.

The same function-call semantics work for both—no new orchestration language required.

## Hardening and Softening

The unified interface enables refactoring in both directions.

### Hardening: Neural → Symbolic

Workers start flexible, then harden as patterns stabilize:

1. **Autonomous creation** — Worker proposes or creates a sub-worker; user approves
2. **Testing** — Run tasks, observe behavior
3. **Iteration** — Refine prompts, add schemas, tune models
4. **Locking** — Pin orchestrators to vetted workers
5. **Migration** — Extract deterministic parts to Python (which can still call workers for fuzzy parts)

**Concrete example**: The pitchdeck examples show a full hardening progression:
- [`pitchdeck_eval`](../examples/pitchdeck_eval/) — All LLM: orchestrator decides file handling and delegates to evaluator
- [`pitchdeck_eval_hardened`](../examples/pitchdeck_eval_hardened/) — Extracted tools: `list_pitchdecks()` replaces LLM slug generation with deterministic Python
- [`pitchdeck_eval_code_entry`](../examples/pitchdeck_eval_code_entry/) — Python orchestration: main loop in code, LLM only called for actual analysis

### Softening: Symbolic → Neural

The common path for softening is **extension**: you need new functionality, you describe it as a spec (or even just user stories), and you plug it into the system as a worker. You can also use an LLM to combine user stories into a coherent spec.

```python
# New capability added by writing a spec
result = await ctx.call("sentiment_analyzer", customer_feedback)
```

The rarer path is **replacement**: rigid code is drowning in edge cases, so you swap it for an LLM call that handles variation gracefully.

**Example**: A Python tool routes support tickets using keyword matching. Edge cases multiply—users describe the same issue in countless ways, and the if/else tree becomes unmaintainable. Replace classification with `ctx.call("ticket_router", ticket_text)`. The worker handles linguistic variation; deterministic rules still enforce valid category codes on the output.

### Hybrid Tools

A common pattern is Python functions that handle deterministic logic but delegate fuzzy parts to focused workers:

```python
@tools.tool
async def evaluate_document(ctx: RunContext[Context], path: str) -> dict:
    # Deterministic: load and validate
    content = load_file(path)
    if not validate_format(content):
        raise ValueError("Invalid format")

    # Neural: delegate ambiguous analysis
    analysis = await ctx.deps.call("content_analyzer", {"input": content})

    # Deterministic: compute final score
    return {"score": compute_score(analysis), "analysis": analysis}
```

The pattern inverts the typical view: rather than "LLM with tools," think "deterministic pipeline that uses LLM where judgment is needed."

## Tool Calls as Syscalls (Approvals)

In llm-do, every tool call from an LLM can be intercepted for potential human approval—at any nesting depth. Think of approvals as **syscalls**: when a worker needs to do something dangerous, execution blocks until the harness grants permission.

Pattern-based rules can auto-approve safe operations (read-only queries, known-safe commands), while risky actions require explicit consent. The goal is progressive trust: start with tight approval requirements, loosen them as confidence grows.

**Approvals reduce risk, not eliminate it.** Prompt injection can trick LLMs into misusing tools you've already approved. Treat approvals as one layer of defense—they catch obvious mistakes and enforce intent, but aren't a security boundary. For real isolation, run in a container or VM. See [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) for the broader threat landscape.

## Tradeoffs

**llm-do is a good fit when you want:**
- Normal-code control flow (branching, loops, retries)
- Fast prototyping that can be progressively hardened
- Tight scoping and tool-level auditability
- Flexibility to refactor between LLM and code as needs evolve

**It may be a poor fit if you need:**
- Durable workflow engine with checkpointing/replay
- Graph visualization as the primary interface
- Distributed orchestration out of the box

If you need durable workflows with automatic retry and state persistence, llm-do can be a component *within* such a system—but it doesn't replace Temporal, Prefect, or similar engines.

## Design Principles

1. **Workers as functions** — Focused, composable units that do one thing well
2. **Unified function space** — Workers and tools call each other freely; LLM vs Python is an implementation detail
3. **Honest abstraction** — Same calling convention across the distribution boundary, but the boundary is visible
4. **Bidirectional refactoring** — Harden prompts to code as patterns stabilize; soften by adding new capabilities via specs
5. **Guardrails by construction** — Tool schema validation and approval enforcement in code, guarding against LLM mistakes
6. **Bounded recursion** — Workers calling workers feels like function calls, with depth limits to prevent runaway recursion and context blowup

## Related Work

**[ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629)** — The foundational pattern: interleave reasoning (LLM) with acting (tool calls). llm-do extends this by making the tool layer itself composable.

**[MRKL Systems](https://arxiv.org/abs/2205.00445)** — Modular reasoning with expert modules. Shares the vision of routing between neural and symbolic components.

**[PAL: Program-Aided Language Models](https://arxiv.org/abs/2211.10435)** — Offloading computation to code. llm-do generalizes this to bidirectional flow.

**[Toolformer](https://arxiv.org/abs/2302.04761)** — LLMs learning when to use tools. llm-do takes the complementary approach: humans define tool boundaries, then progressively harden or soften them.

**[LangGraph](https://langchain-ai.github.io/langgraph/)** — Graph-based agent orchestration. Represents the "graph DSL" approach llm-do contrasts with.

**[OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)** — The standard reference for LLM security risks. Informs llm-do's approval model.

**[Adaptation of Agentic AI](https://arxiv.org/abs/2512.16301)** — Taxonomy for adaptation in agentic systems. Validates the bidirectional refactoring approach. See [detailed analysis](notes/adaptation-agentic-ai-analysis.md).

---

See [`architecture.md`](architecture.md) for implementation details: worker definitions, toolsets, approvals, and the runtime API.
