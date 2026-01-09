# Worker Call Semantics and Recursion Readiness

## Context
We clarified the per-call message history model and discussed whether the
architecture is "recursion-ready" (supporting recursion cleanly if ever needed).

## Findings
- Treat `CallFrame.messages` like local variables: each worker call gets a fresh
  message history unless explicitly passed as an argument.
- Recursion semantics are clean under this model: state flows through explicit
  inputs, not hidden message history. Recursion becomes a normal call-stack
  operation with depth tracking and explicit inputs.
- The runtime is already reentrant (workers can call other workers), so recursion
  is technically supported even if direct self-calls are intentionally excluded.
- The "no self toolset" rule is a policy guardrail to avoid accidental self-call
  loops and name ambiguity, not a structural limitation of the runtime.
- Shared state lives in `Runtime`/`RuntimeConfig` (globals) while messages remain
  per-call (locals), mirroring a call stack.

## Open Questions
- Should we document a standard pattern for explicitly threading message history
  across calls when a caller wants it?
