# ADR-004: Unified Tool Plane for Agents and Entry Functions

**Status:** Accepted

**Date:** 2026-02-01

## Context

llm-do supports multiple execution modes: LLM-driven agents, Python entry functions, and direct scripts. We needed to ensure consistent behavior across these modes while maintaining a clear trust model.

See [unified-entry-function-design.md](background/unified-entry-function-design.md) for the full analysis.

### Two Planes of Execution

All orchestration code operates across two planes:

**Tool Plane** - Observable, instrumented execution:
- `ctx.call()` / toolsets / agent invocations
- Approval wrapping and policy hooks
- Depth tracking and event callbacks
- Tool events emitted for observability

**Raw Python Plane** - Direct execution, no guardrails:
- File I/O, subprocess, network calls done directly in code
- No approvals, no tool events, no policy hooks
- Not observable by the framework

## Decision

Maintain a **unified tool plane** across all execution modes (agents, entry functions, scripts). The key insight: an entry function with access to multiple agents is the same as an "orchestrator agent" - just without the LLM making decisions.

### The Progression Path

| Step | Plane | Who decides | Code trusted? | Notes |
|------|-------|-------------|---------------|-------|
| 1. Agent | Tool | LLM | N/A | Approval gates LLM decisions |
| 2. Entry | Tool | Code | Yes | Trusted code, observable tool calls |
| 3. Script | Tool | Code | Yes | Python embedding without CLI |
| 4. Plain | Raw Python | Code | Yes | Leave observability, own visibility |

**Key insight**: Steps 1-3 all stay in the **tool plane**. This isn't primarily about trust - it's about **smooth refactoring** with identical observable behavior.

### Trust Model

Entry functions (step 2+) are trusted code from the start - they can run arbitrary Python. The tool plane wrapping on `ctx.call()` serves two purposes:

1. **Refactoring smoothness** - identical tool plane behavior means Agent → Entry is a pure refactor
2. **Observability** - visibility into what tool calls the trusted code triggers

This is different from agents (step 1) where the LLM makes decisions and approval gates those decisions.

### Implementation

- Entry toolsets are wrapped for approval per `RunApprovalPolicy`
- `CallFrame.invocation_name` attributes events to the invocation
- Depth is CallFrame stack depth (entry at 0; child agents at 1+)
- Same `ctx.call()` pattern works in entry functions and agents

## Consequences

**Positive:**
- **Smooth refactoring**: Agent → Entry is a pure refactor with identical tool plane behavior
- **Clear trust model**: Entry functions are trusted; tool plane is for parity and observability
- **Consistent interface**: `ctx.call()` works the same everywhere
- **Flexible deployment**: Script mode is orthogonal - use when Python embedding is needed
- **Easier testing**: Same tool plane means same test setup

**Negative:**
- Mental model requires understanding two planes
- Raw Python escapes the tool plane (intentional, but needs documentation)
- Script mode currently requires registry linking for named toolsets

**Operational Notes:**
- Tool plane behavior (approval policy, events, depth) must be identical across steps 1-3
- Step 4 leaves the tool plane by default; caller decides whether to opt back in
- Attachment paths resolve relative to the runtime project root
- Raw Python code in any step is outside the tool plane
