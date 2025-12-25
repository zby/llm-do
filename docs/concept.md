# llm-do: Concept and Design

> The way to build useful non-deterministic systems more complex than chat is making them deterministic at key spots.

## The Problem

Existing approaches to agentic systems have characteristic failure modes:

- **Monolithic prompts** — One giant system prompt tries to handle everything. As capabilities grow, the prompt becomes unmaintainable. Context gets bloated with irrelevant instructions. Behavior becomes unpredictable.

- **Graph DSLs** — You define nodes and edges upfront, then an engine runs the graph. Refactoring means redrawing edges. Dynamic routing requires escape hatches. The abstraction fights you when requirements change.

- **Pure tooling** — Deterministic code can't handle ambiguity. Edge cases multiply into unmaintainable conditionals. You end up reimplementing judgment in if-statements.

llm-do addresses this by treating workers (LLM agents) and tools (Python functions) as interchangeable functions in a unified call graph.

## Core Idea

**Workers are functions.**

A worker is a prompt + configuration + tools, packaged as an executable unit. Workers call other workers and Python tools interchangeably—LLM reasoning and deterministic code interleave freely.

**Quick example**: A `file_organizer` worker renames files to consistent formats. Initially it decides naming conventions via LLM reasoning—flexible but slow. After observing patterns, you extract `sanitize_filename()` to Python: deterministic, tested, fast. The worker still handles ambiguous cases ("is this a date or a version number?"), but the common path is now code. Approvals gate the actual `mv` operations throughout.

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

## Harness, Not Graph

Most agent frameworks are **graph DSLs**—you define nodes and edges (DAGs, state machines, YAML orchestration), and an engine runs the graph. llm-do is an **imperative harness**: your code owns control flow, llm-do intercepts at the tool layer.

Need a fixed sequence? Write a Python script that calls workers. Need dynamic routing? Let the LLM decide which worker to call. The same function-call semantics work for both—no new abstractions to learn.

### Tradeoffs

**What you gain:**
- **Flexibility** — Use a real programming language for control flow, not a constrained DSL
- **Local reasoning** — Each worker is self-contained; no global graph to trace
- **Easier refactoring** — Extract code, inline workers, change structure without updating edge definitions
- **Tool-layer interception** — Approvals, logging, and policies apply uniformly at call boundaries

**What you don't get:**
- **Durable execution** — No built-in checkpointing or replay; if the process dies, you restart
- **Visual workflow editing** — No drag-and-drop graph builder
- **Distributed orchestration** — Single-process by default; for distributed workflows, integrate an external engine

If you need durable workflows with automatic retry and state persistence, llm-do can be a component *within* such a system—but it doesn't replace Temporal, Prefect, or similar engines.

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

**Concrete example**: The pitchdeck examples show a full hardening progression:
- [`pitchdeck_eval`](../examples/pitchdeck_eval/) — All LLM: orchestrator decides file handling and delegates to evaluator
- [`pitchdeck_eval_hardened`](../examples/pitchdeck_eval_hardened/) — Extracted tools: `list_pitchdecks()` replaces LLM slug generation with deterministic Python
- [`pitchdeck_eval_code_entry`](../examples/pitchdeck_eval_code_entry/) — Python orchestration: main loop in code, LLM only called for actual analysis

### Softening: Symbolic → Neural

When rigid code needs flexibility, replace deterministic logic with worker calls:

**Example**: A Python tool parses config files with regex. Edge cases multiply, regex becomes unmaintainable. Replace parsing with `ctx.call_tool("config_parser", raw_text)`. The worker handles ambiguous formats; deterministic validation still runs on the output.

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

Part of that scaffold is **human oversight**. The ideal would be fully autonomous execution—let the agent run to completion without interruption. But experience shows this is premature: LLMs make mistakes, misinterpret intent, and occasionally attempt dangerous operations. In llm-do, every tool call from an LLM is intercepted for potential human approval—at any nesting depth. Think of approvals as **syscalls**: when a worker needs to do something dangerous, execution blocks until the harness grants permission. Pattern-based rules can auto-approve safe operations (read-only queries, known-safe commands), while risky actions require explicit consent. The goal is progressive trust: start with tight approval requirements, loosen them as confidence grows.

**Approvals reduce risk, not eliminate it.** Prompt injection can trick LLMs into misusing tools you've already approved. Treat approvals as one layer of defense—they catch obvious mistakes and enforce intent, but aren't a security boundary. For real isolation, run in a container or VM. See [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) for the broader threat landscape.

A common need is **hybrid tools**: Python functions that handle deterministic logic but delegate fuzzy parts to focused workers:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.ctx_runtime import Context

tools = FunctionToolset()

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

## Design Principles

1. **Workers as functions** — Focused, composable units that do one thing well

2. **Unified function space** — Workers and tools call each other freely; LLM vs Python is an implementation detail

3. **Bidirectional refactoring** — Harden prompts to code as patterns stabilize; soften rigid code to prompts when flexibility is needed

4. **Guardrails by construction** — Tool schema validation and approval enforcement in code, guarding against LLM mistakes

5. **Recursive composability** — Workers calling workers feels like function calls, with bounded depth to prevent runaway recursion and context blowup

## Related Research

**[Adaptation of Agentic AI](https://arxiv.org/abs/2512.16301)** — Taxonomy for adaptation in agentic systems. Validates llm-do's bidirectional refactoring approach and suggests data-driven extensions: failure logging, offline analysis, confidence signaling. See [detailed analysis](notes/adaptation-agentic-ai-analysis.md) for proposed features.

**[ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629)** — The foundational pattern llm-do builds on: interleave reasoning (LLM) with acting (tool calls). llm-do extends this by making the tool layer itself composable—tools can invoke workers, creating nested reasoning chains.

**[Toolformer](https://arxiv.org/abs/2302.04761)** — Demonstrates LLMs learning when to use tools. llm-do takes the complementary approach: humans define tool boundaries, then progressively harden or soften them based on observed behavior.

**[OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)** — The standard reference for LLM security risks. Informs llm-do's approval model and the security posture described above.

---

See [`architecture.md`](architecture.md) for implementation details: worker definitions, toolsets, approvals, and the runtime API.
