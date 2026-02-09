# RLM (Recursive Language Model) Explained

## The Problem

LLMs have context windows. When you need to analyze a large document — say 100k tokens
of code — you can stuff it all into the prompt, but the LLM struggles to reason
precisely over that much text at once. You need a way to break the problem down.

## The Everything-in-Memory Regime

To understand RLMs, you first need to understand the regime they operate in — because
it would seem very strange to any programmer.

In normal software, large data lives on disk or in a database. You read what you need,
process it, move on. No one loads a 100k-token codebase into a function's argument
list. But the RLM benchmarks (arXiv:2512.24601) work exactly this way: the entire
input is handed to the system as a single blob. No filesystem, no tools, no database.
Just "here's your data, answer the question."

In this regime, you only have two places to put the data:

1. **In the prompt** — the LLM sees all of it in its context window
2. **In a REPL variable** — the data lives in the Python namespace; the LLM accesses
   it by writing code

The paper's baseline, "CodeAct + Sub-calls," takes option 1. RLM takes option 2. The
results are dramatic:

| Benchmark    | CodeAct+Sub-calls | RLM   |
|--------------|-------------------|-------|
| CodeQA       | 24.0%             | 62.0% |
| OOLONG       | 40.0%             | 56.5% |
| OOLONG-Pairs | 28.4%             | 58.0% |

This is less surprising than it looks. Of course you win by not cramming 100k tokens
into the prompt. Any programmer's first instinct — read the data from disk in pieces —
would achieve the same thing. But in the artificial benchmark regime, that option
doesn't exist. RLM's "context as variable" trick is an optimization *within* this
constrained regime, solving a problem that real agents with file-reading tools don't
have.

## What RLMs Actually Do

Given that regime, the RLM recipe has three ingredients:

**1. Model-driven REPL.** The LLM emits code blocks. The system executes them and
feeds output back. The LLM decides what to write next. This repeats until the LLM
signals it's done (via a `FINAL("answer")` convention).

**2. Context as a variable.** The large input data is loaded as a Python variable in
the REPL's namespace. The LLM can't see it directly — it has to write code like
`print(context[:500])` to peek at its own input. Strange, but it keeps the context
window clean for reasoning.

**3. Recursive sub-calls.** A function like `recursive_llm(query, context)` is
injected into the REPL. Calling it spawns a fresh LLM conversation with its own REPL.
This enables divide-and-conquer: the LLM writes map-reduce over sub-problems, where
each map step is itself an LLM call.

The key move is that **orchestration happens in code, not in the prompt**:

```
Naive agent approach:
  LLM sees chunk1 → summarizes → result stays in context
  LLM sees chunk2 → summarizes → result stays in context
  LLM sees chunk3 → summarizes → result stays in context
  LLM sees all 3 summaries → produces final answer

RLM approach:
  LLM writes code:
    results = []
    for chunk in chunks:
        summary = recursive_llm("summarize this", chunk)
        results.append(summary)
    FINAL("\n".join(results))
```

The for-loop runs in Python. Intermediate results never enter the LLM's context. Only
the final aggregation comes back.

## A Concrete Example

Suppose you want to find security vulnerabilities across a large codebase:

```python
# The LLM writes this in the REPL:
files = context.split("---FILE BOUNDARY---")
vulnerabilities = []

for file_content in files:
    # Each call spawns a fresh LLM with its own REPL
    result = recursive_llm(
        "Find security vulnerabilities in this code. Return a JSON list.",
        file_content
    )
    vulnerabilities.extend(json.loads(result))

# Deduplicate and rank
unique = {v['description']: v for v in vulnerabilities}
ranked = sorted(unique.values(), key=lambda v: v['severity'], reverse=True)

FINAL(json.dumps(ranked[:10], indent=2))
```

The parent LLM never sees the individual file contents or per-file results in its
context. It only sees the final top-10 list.

## How Novel Is This?

None of the ingredients are new. The underlying primitive — a tool that calls an LLM —
has been available in agent frameworks for a long time. PydanticAI has supported agent
delegation (calling `other_agent.run(...)` inside a tool function) since its early
releases. Many coding agents (Cursor, Claude Code, Devin) spawn sub-agents that can
recursively invoke further sub-agents. You could have built an RLM on top of PydanticAI
long before the term existed.

What RLM implementations contribute is a specific *recipe* — the right proportions of
known ingredients. Discovering the right proportions matters; the combination produces
results that the individual ingredients don't. But it is a usage pattern on top of
existing capabilities, not a new computational primitive.

The benchmark framing also flatters RLM by comparing it against an approach no
programmer would choose. In any real system, data lives on disk and the agent reads
slices via tools. The "context as variable" trick is clever within the everything-in-
memory regime, but in practice it's just a constrained version of what file-reading
tools already provide.

## Limitations

- **Ephemeral code** — Everything the LLM writes is discarded after each run. Patterns
  discovered during analysis can't be reused. Every query starts from scratch.
- **Pure computation only** — RLM code reads data and produces answers but causes no
  side effects. No file writes, no API calls, no real-world actions.
- **Sandbox trust model** — Because code is ephemeral and pure, there's no approval
  system. The sandbox *is* the safety boundary. This works for analysis but not for
  agents that do real work.

## Existing Implementations

- **ysz/recursive-llm** — Full implementation with RestrictedPython sandboxing, depth
  limits, and async support.
- **alexzhang13/rlm-minimal** — Stripped-down version, `exec`/`eval` based, OpenAI
  only. Good for understanding the pattern.
- **Shesha** — Adds a document ingestion pipeline on top of the RLM pattern.
