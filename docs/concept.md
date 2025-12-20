# llm-do: Concept and Design

> The way to build useful non-deterministic systems more complex than chat is making them deterministic at key spots.

## Core Idea

**Workers are functions.**

A worker is a prompt + configuration + tools, packaged as an executable unit. Workers call other workers and Python tools interchangeably—LLM reasoning and deterministic code interleave freely.

## Unified Function Space

Workers and tools are the same abstraction. Both are functions that can call each other in any combination—just like in a regular program. Whether a function is implemented as an LLM agent loop or Python code is an implementation detail; the calling convention is identical.

This is neuro-symbolic computing in practice:

```
LLM ──calls──▶ Tool ──calls──▶ LLM ──calls──▶ Tool ...
     reason         execute         reason
     decide         compute         decide
```

Each component plays to its strengths:

| Component | Strengths |
|-----------|-----------|
| Neural (LLM) | Flexible reasoning, handles ambiguity, contextual |
| Symbolic (Tool) | Deterministic, precise, cheap, auditable |

The question isn't "LLM or code?" but "how much of each, and where?"

```
Pure Python ◄───────────────────────────────────────────► Pure Worker
(all symbolic)                                            (all neural)
      │                        │                               │
 compute_hash           smart_refactor                  code_reviewer
                    (deterministic flow,
                     calls LLM when stuck)
```

Any component can slide along this spectrum as requirements evolve.

## No Workflow DSL

Unlike frameworks that require special languages for defining agent workflows (DAGs, state machines, YAML orchestration), llm-do uses plain Python.

Need a fixed sequence? Write a Python script that calls workers. Need dynamic routing? Let the LLM decide which worker to call. The same function-call semantics work for both—no new abstractions to learn.

## Bidirectional Refactoring

The unified interface enables refactoring in both directions:

### Hardening: Neural → Symbolic

Workers start flexible, then harden as patterns stabilize:

1. **Autonomous creation** — Worker creates sub-worker, user approves
2. **Testing** — Run tasks, observe behavior
3. **Iteration** — Refine prompts, add schemas, tune models
4. **Locking** — Pin orchestrators to vetted workers
5. **Migration** — Extract deterministic parts to Python (which can still call workers for the fuzzy parts)

**Example**: An orchestrator creates an `evaluator` worker. Over weeks, you refine its prompt, add a structured output schema, then extract the scoring math to a Python function. The worker now calls `compute_score()`—the math is deterministic and tested.

**Concrete example**: Compare [`examples/pitchdeck_eval`](../examples/pitchdeck_eval/) with [`examples/pitchdeck_eval_hardened`](../examples/pitchdeck_eval_hardened/). The original has the LLM generate file slugs; the hardened version extracts this to a `list_pitchdecks()` Python tool using the `python-slugify` library—deterministic, tested, no LLM variability.

### Softening: Symbolic → Neural

When rigid code needs flexibility, replace deterministic logic with worker calls:

**Example**: A Python tool parses config files with regex. Edge cases multiply, regex becomes unmaintainable. Replace parsing with `ctx.deps.call_worker("config_parser", raw_text)`. The worker handles ambiguous formats; deterministic validation still runs on the output.

### The Hybrid Pattern

In practice, **LLM calling tools is the dominant pattern**—it's what most people see when they use agentic systems. An LLM reasons about a task, decides which tool to invoke, and interprets the results.

But look closer: even this "LLM-driven" pattern is wrapped in deterministic code. The library handles the agent loop, validates tool calls, enforces schemas, manages retries. The LLM operates within a scaffold:

```
┌─────────────────────────────────────────────────────┐
│  Deterministic wrapper (library/framework)          │
│  ┌───────────────────────────────────────────────┐  │
│  │  LLM reasoning                                │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  Tool calls (deterministic execution)  │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Part of that scaffold is **human oversight**. The ideal would be fully autonomous execution—let the agent run to completion without interruption. But experience shows this is premature: LLMs make mistakes, misinterpret intent, and occasionally attempt dangerous operations. In llm-do, every tool call from an LLM is intercepted for potential human approval—at any nesting depth. Pattern-based rules can auto-approve safe operations (read-only queries, known-safe commands), while risky actions require explicit consent. The goal is progressive trust: start with tight approval requirements, loosen them as confidence grows.

A common need is **hybrid tools**—Python functions that handle deterministic logic but delegate fuzzy parts to focused workers:

```python
async def evaluate_document(ctx: RunContext[ToolContext], path: str) -> dict:
    # Deterministic: load and validate
    content = load_file(path)
    if not validate_format(content):
        raise ValueError("Invalid format")

    # Neural: delegate ambiguous analysis
    analysis = await ctx.deps.call_worker("content_analyzer", content)

    # Deterministic: compute final score
    return {"score": compute_score(analysis), "analysis": analysis}
```

The pattern inverts the typical view: rather than "LLM with tools," think "deterministic pipeline that uses LLM where judgment is needed."

## Design Principles

1. **Workers as functions** — Focused, composable units that do one thing well

2. **Unified function space** — Workers and tools call each other freely; LLM vs Python is an implementation detail

3. **Bidirectional refactoring** — Harden prompts to code as patterns stabilize; soften rigid code to prompts when flexibility is needed

4. **Guardrails by construction** — Attachment validation and approval enforcement in code, guarding against LLM mistakes

5. **Recursive composability** — Workers calling workers feels like function calls, up to 5 levels deep

## Related Research

**[Adaptation of Agentic AI](https://arxiv.org/abs/2512.16301)** presents a taxonomy for adaptation in agentic systems that validates llm-do's bidirectional refactoring approach and suggests data-driven extensions—failure logging, offline analysis, and confidence signaling. See [detailed analysis](notes/adaptation-agentic-ai-analysis.md) for proposed features.

---

See [`architecture.md`](architecture.md) for implementation details: worker definitions, toolsets, approvals, and the runtime API.
