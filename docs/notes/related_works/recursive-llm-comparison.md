# Recursive LLM (ysz/recursive-llm) comparison

## Context

We need a concrete read of the ysz/recursive-llm implementation to compare with llm-do,
especially around what they mean by "recursion" and whether approvals or reentrancy are
part of the design.

## Different Starting Points

**recursive-llm** starts from a specific problem: processing unbounded context (100k+ tokens)
without context rot. Their solution: let the LLM write Python code that chunks and recursively
processes sub-contexts.

**llm-do** starts from a different insight: **stabilizing** (see `docs/theory.md`). The core
idea is that LLM applications evolve by progressively converting stochastic behavior into
deterministic code:

```
Stochastic (prompt)  →  Deterministic (code)
         ↑                      ↓
         └── soften ←── stabilize ──┘
```

When you observe an LLM doing something consistently, you extract it to code. When code
becomes too rigid for edge cases, you soften it back to an LLM call. The system breathes
between these modes.

### How Recursion Emerged

llm-do didn't start with recursion as a goal. It emerged from following software's natural
structure:

1. **Software is recursive.** Functions call functions. Modules import modules. Decomposition
   is fractal.

2. **Stabilizing preserves structure.** When you extract a piece of prompt behavior into a
   tool or worker, it should be callable the same way the LLM was calling it conceptually.

3. **Workers calling workers is natural.** If a complex task decomposes into subtasks, and
   each subtask can be a worker, then workers need to call workers.

4. **No DSL walls.** The refactoring shouldn't stop because you hit framework limitations.
   Prompt → worker → tool → Python code should be a continuous spectrum.

Recursion wasn't the point. **Seamless refactoring** was the point. Recursion is just what
happens when you follow software's structure without artificial boundaries.

## Findings
- Repo: `https://github.com/ysz/recursive-llm` (local clone at `../recursive-llm`)
- Core abstraction is a single `RLM` class with `completion()` / `acompletion()` that runs
  a model-in-the-loop REPL until a `FINAL(...)` statement is emitted.
- "Recursion" is implemented as a `recursive_llm(sub_query, sub_context)` function injected
  into the REPL environment; it creates a new `RLM` instance at `_current_depth + 1` and
  calls `sub_rlm.acompletion(...)`. This is algorithmic recursion with fresh instances,
  not reentrant execution on the same object.
- The REPL is synchronous. If already inside an event loop, recursive calls use a
  `ThreadPoolExecutor` + `asyncio.run` to execute the async subcall in a new loop.
- Context is stored in a Python variable (`context`) rather than being embedded in the
  prompt; the system prompt only tells the model how to access it.
- Sandboxing is via RestrictedPython and a whitelist of safe builtins/modules. There are
  no explicit toolsets, no file/network tools, and no approval boundary.
- Depth and iteration limits exist (`max_depth`, `max_iterations`), but stats/usage are
  per-instance (no global aggregation across recursion levels).

### Implications vs llm-do
- llm-do recursion is explicit worker/tool delegation with per-call frames; RLM recursion
  is model-driven subcalls over sub-contexts inside a REPL.
- llm-do has a defined trust boundary with approvals for LLM-initiated tools; recursive-llm
  has no approvals because it exposes no side-effectful tools.
- llm-do isolates per-call state via `CallFrame`; recursive-llm isolates state by creating
  new `RLM` instances per recursive call.

## Open Questions
- Do we want an RLM-style REPL toolset (stateful Python exec) as an example or built-in?
- If we add a REPL toolset, should approvals gate arbitrary code execution or only
  side-effect tools exposed within that environment?
- Should we add a long-context exploration example that mimics `context` as a variable,
  or keep long-context handling out of scope for now?

## Comparison Summary

| Aspect | recursive-llm | llm-do |
|--------|---------------|--------|
| **Core insight** | LLM can write recursive algorithms | Stabilize stochastic → deterministic |
| **Recursion** | Single function: `recursive_llm(q, ctx)` | Named workers with schemas |
| **Tools** | Python REPL only | Filesystem, shell, web, custom |
| **Composition** | Implicit (code writes code) | Explicit (worker declares toolsets) |
| **Trust boundary** | None (sandboxed REPL) | Approval system per tool |
| **Use case** | Long context processing | General task decomposition |

## Conclusion

recursive-llm and llm-do both support "true recursion" (LLM calls trigger new LLM conversations),
but from different motivations:

- **recursive-llm** solves a specific problem (context length) with a clever trick (REPL + recursion).
  The LLM becomes a programmer that writes its own divide-and-conquer algorithms.

- **llm-do** provides a framework for evolving LLM applications. Start with prompts, stabilize to
  code as patterns emerge, soften when rigidity hurts. Recursion is a consequence of treating
  workers like functions in a codebase—not a feature, but an emergent property of good structure.

The key differentiator: llm-do's refactoring is **seamless across the stochastic-deterministic
boundary**. There's no DSL wall where you have to stop extracting or composing. A worker can
become a tool, a tool can become a worker, and the calling convention stays the same.
