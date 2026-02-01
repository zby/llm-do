# ADR-006: Runtime Core vs Simpler Runtime

**Status:** Accepted

**Date:** 2026-02-01

## Context

With the runner/harness split out, the remaining question is the runtime itself:
could we keep a runner with similar capabilities while drastically simplifying
the runtime? PydanticAI already supports delegation, programmatic hand-off,
graphs, and deep-agent patterns. It also provides usage tracking and external
observability (Logfire/OTel). In principle, an agent can be used as a tool by
calling a delegate `Agent` inside another agent's tool function.

The key objection is: if "agent as tool" is already possible in vanilla
PydanticAI, why accept llm-do's runtime complexity at all?

The runtime in llm-do currently provides:
- A shared registry for agents and toolsets (name-based dispatch).
- Per-call state and isolation (`CallContext`, `CallFrame`, `CallScope`).
- Toolset instantiation and cleanup per call.
- Approval interception and policy at the tool-call boundary.
- Depth enforcement and consistent event streaming across nested calls.
- Entry functions that orchestrate agents without an LLM.

See `docs/notes/llm-do-vs-pydanticai-runtime.md` for the detailed comparison.

### Alternatives Considered

1. **Runner-only (no runtime):**
   - Directly wire PydanticAI `Agent` objects and call them from tools or app
     code.
   - Pros: minimal surface area.
   - Cons: no name-based dispatch, no late binding, manual dependency passing,
     no uniform tool lifecycle, approvals become ad hoc per toolset, and the
     call surface is split between Python calls and tool calls.

2. **Thin runtime (registry + entry resolution only):**
   - Keep declarative loading but defer all lifecycle, approvals, and call
     context handling to PydanticAI tools and app code.
   - Pros: fewer runtime types.
   - Cons: runner re-implements the missing pieces (scopes, depth, approvals),
     or those guarantees are dropped, leading to inconsistent behavior.

### Decision Drivers

- **Unified call surface:** tools and agents must be callable by name so callers
  do not depend on concrete implementations.
- **Late binding:** components should be registered after callers are defined,
  allowing agent-to-code refactors without prompt changes.
- **Isolation by default:** message history, tool instances, and depth limits
  must be per-call and deterministic.
- **Central policy:** approval rules and event callbacks should be enforced
  consistently across nested calls.
- **Deterministic orchestration:** entry functions should orchestrate agents
  in the same tool plane as LLM-driven calls.
- **Cross-cutting behavior:** approvals, logging, and usage aggregation should
  apply uniformly regardless of whether a tool calls code or another agent.

## Decision

Keep the current runtime split (shared `Runtime` + per-call `CallContext` and
`CallFrame`) because it is the minimal structure that preserves the unified
tool/agent call surface, per-call isolation, and centralized approval policy.

The "runner-only" or "thin runtime" alternatives either drop these guarantees
or recreate them in the runner, which effectively reintroduces a runtime under
another name.

## Consequences

**Positive:**
- Call sites remain stable while components migrate between agent and code.
- Approvals, depth limits, and event streams remain consistent across nested
  calls, regardless of entry type.
- Toolset state is isolated and cleaned up deterministically.
- "Agent as tool" becomes *uniform* instead of ad hoc: the LLM calls a name,
  and the runtime resolves whether it is an agent or a Python tool.

**Negative:**
- Runtime concepts add complexity for small projects.
- Tight coupling to PydanticAI execution semantics requires maintenance.

## Rationale: Why "Agent as Tool" Is Not Enough

PydanticAI delegation shows that an agent can call another agent inside a tool,
but this is still **manual wiring** in application code. llm-do's runtime makes
the same idea **systemic**:

- **Name-based dispatch, not object references.** The LLM calls a tool name.
  The runtime decides whether that name is backed by an agent or Python code.
  This enables refactors (agent -> tool or tool -> agent) without prompt changes.
- **Uniform interception.** Approvals, logging, and usage aggregation apply to
  both tool calls and agent calls. In vanilla delegation, you must remember to
  pass `ctx.usage` and wrap approval logic in each tool.
- **Isolation by default.** Each agent call gets a fresh call frame and toolset
  instances. Vanilla delegation often shares objects and deps implicitly unless
  the developer is careful.
- **Declarative loading.** `.agent` files + manifest registration allow late
  binding and CLI/TUI composition without custom glue.

In short, PydanticAI already *permits* agent-as-tool, but llm-do's runtime makes
it *predictable, observable, and refactor-friendly* across a whole project.
