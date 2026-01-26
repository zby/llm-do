# Experiment runtime without Worker class

## Context
We want to remove the `Worker` class and make the experiment runtime (`deps`-as-runtime)
the primary execution surface. The question is how much `CallContext`-style deps
should absorb and what architecture replaces the Worker responsibilities.

## Findings
- `CallContext` alone does not cover lifecycle, toolset cleanup, or prompt/agent
  orchestration; those behaviors live in `Worker` today.
- Removing `Worker` means relocating its responsibilities into:
  - a call-scope/lifecycle abstraction (build toolsets per call, run agent, cleanup),
  - an `Entry` abstraction (agents + Python callables),
  - a runtime state object for usage + message log aggregation.
- The experiment already has a minimal `AgentRuntime` but lacks:
  - run-scoped sinks,
  - call-scope boundaries,
  - entry resolution and model compatibility logic.
- `CallContext` can remain a facade as long as it continues to wrap shared run-state
  (`Runtime`) plus per-call state (`CallFrame`); that design still scales if Worker
  goes away.

## Toolset Instantiation: CallScope vs Runtime
If `Worker` is removed, I favor toolset instantiation in `CallScope` (or a CallSite
equivalent) rather than in the deps/runtime object:

- **Lifecycle alignment:** CallScope is already responsible for per-call lifecycle and
  cleanup, so it is the natural place to ensure toolsets are torn down after the run.
- **Testability:** CallScope-bound toolset creation makes it easier to test “per call”
  behavior without relying on global runtime state.
- **Runtime as facade:** If the runtime stays a facade over shared state, keeping
  construction in CallScope preserves the separation between "shared run state" and
  "per-call resources".

This implies keeping a small helper (e.g., `ToolsetResolver`) owned by runtime (or
passed into CallScope) so CallScope can ask for toolsets when it starts, but CallScope
should own instantiation and cleanup ordering.

## Open Questions
- How far should the `deps` object go in exposing the tool plane (`call_tool`)
  versus keeping that in a separate facade?
- What is the minimal `Entry` interface for PydanticAI agents vs. `@entry` functions
  that keeps the runtime decoupled from worker-like classes?

## Conclusion
Pending. Proposed next step is to sketch a minimal `Entry` + `CallScope` API for the
experiment runtime and then map `Worker` responsibilities onto those abstractions.
