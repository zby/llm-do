# llm-do: Concept and Design

## Core Idea

**Workers are functions.**

A worker is a prompt + configuration + tools, packaged as an executable unit. Workers call other workers and Python tools interchangeably—LLM reasoning and deterministic code interleave freely.

**No workflow DSL.** Unlike frameworks that require special languages for defining agent workflows (DAGs, state machines, YAML orchestration), llm-do uses plain Python. Need a fixed sequence? Write a Python script that calls workers. Need dynamic routing? Let the LLM decide which worker to call. The same function-call semantics work for both—no new abstractions to learn.

## Neuro-Symbolic Computing

**Workers and tools are the same abstraction.** Both are functions that can call each other in any combination—just like in a regular program. Whether a function is implemented as an LLM agent loop or Python code is an implementation detail; the calling convention is identical.

**Dual recursion**:
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

## Progressive Hardening (and Softening)

The unified interface enables **bidirectional refactoring**:

### Hardening: Neural → Symbolic

Workers start flexible, then harden as patterns stabilize:

1. **Autonomous creation** — Worker creates sub-worker, user approves
2. **Testing** — Run tasks, observe behavior
3. **Iteration** — Refine prompts, add schemas, tune models
4. **Locking** — Pin orchestrators to vetted workers
5. **Migration** — Extract deterministic parts to Python (which can still call workers for the fuzzy parts)

**Example**: An orchestrator creates an `evaluator` worker. Over weeks, you refine its prompt, add a structured output schema, then extract the scoring math to a Python function. The worker now calls `compute_score()`—the math is deterministic and tested.

### Softening: Symbolic → Neural

When rigid code needs flexibility, replace deterministic logic with worker calls:

**Example**: A Python tool parses config files with regex. Edge cases multiply, regex becomes unmaintainable. Replace parsing with `ctx.deps.call_worker("config_parser", raw_text)`. The worker handles ambiguous formats; deterministic validation still runs on the output.

### The Hybrid Pattern

Hardening often produces **hybrid tools**—Python functions that handle deterministic logic but delegate fuzzy parts to focused workers:

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

Tested Python for the predictable parts, LLM reasoning only where needed.

## The Refactoring Spectrum

```
Pure Python ◄─────────────────────────► Pure Worker
(all symbolic)                          (all neural)

  compute_hash ── smart_refactor ── code_reviewer
       │               │                   │
       │         hybrid: mostly            │
       │         deterministic,       full LLM
       │         calls LLM when stuck      │
       │                                   │
   no LLM ◄───────────────────────────► only LLM
```

Any component can slide along this spectrum as requirements evolve.

## Design Principles

1. **Workers as functions** — Focused, composable units that do one thing well

2. **Unified function space** — Workers and tools call each other freely; LLM vs Python is an implementation detail

3. **Bidirectional refactoring** — Harden prompts to code as patterns stabilize; soften rigid code to prompts when flexibility is needed

4. **Guardrails by construction** — Attachment validation and approval enforcement in code, guarding against LLM mistakes

5. **Recursive composability** — Workers calling workers feels like function calls, up to 5 levels deep

---

See [`architecture.md`](architecture.md) for implementation details: worker definitions, toolsets, approvals, and the runtime API.
