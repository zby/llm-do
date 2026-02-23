# ADR-005: Runner Harness vs PydanticAI CLAI

**Status:** Accepted

**Date:** 2026-02-01

## Context

PydanticAI ships a user-facing CLI and web UI called **clai**. It supports:
- chat mode with a selected model
- custom agents loaded via `module:variable`
- a simple web UI (`clai web`)
- optional built-in tools and extra instructions

This raises a narrower question than runtime shape: why does llm-do include its
own **runner/harness** instead of using clai as the user-facing app? Here
"runner" means the CLI/TUI entrypoint that wires a single run: loading project
configuration, constructing a runtime, streaming events, and mediating approvals.
Runtime structure and tradeoffs are covered separately in ADR-006.

### Decision Drivers

- **Project loading:** `.agent` files, manifests, and toolset factories must be
  resolved into a runnable entry without custom Python glue.
- **Multi-agent projects:** the runner must load and route across a registry of
  named agents and tools, not a single `Agent` instance.
- **Tool approvals:** file/shell tools require blocking approvals and policy
  enforcement at the run boundary.
- **Event streaming:** tool calls/results and nested agent activity must be
  visible to the UI with consistent semantics.
- **Entry flexibility:** runs may start from an agent or a deterministic entry
  function, with identical orchestration behavior.

## Decision

Keep a **runner/harness layer** for CLI/TUI runs rather than adopting clai. clai
is optimized for single-agent chat and simple web UI flows, while llm-do needs a
project-aware runner that:

- resolves entries from manifests and `.agent` files
- wires a registry of agents/toolsets for name-based dispatch
- enforces approval policies for dangerous tools
- streams nested tool/agent events for the UI

The runner is intentionally thin and delegates execution to the runtime. Direct
PydanticAI usage remains available, but the CLI/TUI path uses the runner to
guarantee consistent project-level behavior.

## Consequences

**Positive:**
- Interactive runs match the project model (manifest + `.agent` files) rather than
  a single imported `Agent`.
- Approval UX and event streaming behave identically across CLI/TUI entry points.
- Multi-agent projects do not require bespoke Python wiring.

**Negative:**
- Adds an extra layer compared to using clai directly for one-off chats.
- Runner behavior must stay aligned with runtime and PydanticAI event changes.
