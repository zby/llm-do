# Theoretical Foundation

> llm-do's design is grounded in the [underspecified instructions framing](https://github.com/zby/commonplace/blob/main/kb/notes/agentic-systems-interpret-underspecified-instructions.md): LLM-based systems have two distinct properties — semantic underspecification (natural language specs admit multiple valid interpretations) and execution indeterminism (sampling noise) — and useful systems manage the boundary between underspecified and precise semantics through stabilising (committing to one interpretation in code) and softening (adding new capability via LLM). This document covers llm-do's specific contribution: a hybrid VM that makes that boundary easy to cross.

## The Hybrid VM

llm-do's specific contribution is a **hybrid VM** that makes the boundary between underspecified and precise semantics easy to cross.

The hybrid VM unifies LLM execution (neural) and Python execution (symbolic) under a single calling convention at the tool layer the LLM sees. The VM can dispatch to either; callers don't need to know which.

### Why unified calling matters

If an LLM call looks completely different from a tool call, refactoring across the semantic boundary is painful. Prompt structure fights the change.

The hybrid VM solves this:
- Agents and tools share a single tool namespace for the LLM
- Prompt call sites stay stable when implementations move across the boundary

```python
# LLM tool call (prompt) stays the same:
# tool: ticket_classifier(...)

# Python orchestration today (neural)
analysis = await ctx.deps.call_agent("ticket_classifier", ticket_text)

# Python orchestration tomorrow (symbolic)
analysis = ticket_classifier(ticket_text)
```

The LLM-facing calling convention is unified. The implementation moved from underspecified to precise semantics; prompts don't change.

For more on this design, see [Unified calling conventions enable bidirectional refactoring](../kb/notes/unified-calling-conventions-enable-bidirectional-refactoring.md).

### Name-based dispatch

Unified calling requires **name-based dispatch**: components are identified by string name rather than direct object reference.

Why names?

- **Dynamic resolution.** When an LLM decides to call another component, it outputs a string. You need name-based lookup to resolve that string to an implementation.
- **Late binding.** The called component doesn't need to exist when the caller is defined.
- **Implementation-agnostic interfaces.** A name like `ticket_classifier` can resolve to an agent today and a Python function tomorrow.

Direct reference couples caller to implementation. Name-based dispatch keeps the interface stable while implementations change.

## The Harness

On top of the hybrid VM, llm-do adds a **harness** — an orchestration layer that intercepts operations, manages approvals, and controls execution flow.

The VM enables the harness by providing interception points. Name-based dispatch means every call goes through a lookup layer that can wrap, modify, or gate the invocation. The VM provides the machinery; the harness uses it to implement policies.

The harness enables:
- **Approval workflows**: Human-in-the-loop for sensitive operations
- **Composition**: Components with underspecified and precise semantics interleave freely
- **Testing strategies**: Swap implementations for testing
- **Auditability**: Tool-level logging and inspection

The harness is llm-do's specific implementation choice. The hybrid VM concept stands independently — other systems could build different orchestration layers on the same interception points.

## Tradeoffs

**llm-do is a good fit when:**
- You want normal Python control flow (branching, loops, retries)
- You're prototyping and will stabilise as patterns emerge
- You need tool-level auditability and approvals
- You want flexibility to refactor between LLM and code

**It may be a poor fit when:**
- You need durable workflows with checkpointing/replay
- Graph visualization is your primary interface
- You need distributed orchestration out of the box

llm-do can be a component *within* durable workflow systems (Temporal, Prefect), but doesn't replace them.

---

See also: [architecture](architecture.md) for internal structure, [reference](reference.md) for API.
