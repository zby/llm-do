# Compiler Analogy for Worker Scopes

## Context
We previously had two notes: "messages as locals" and "toolsets as import tables". The
architecture is now centered on EntryRegistry -> Runtime -> CallFrame, and
recursion is a supported pattern (including self-recursion via toolsets).
This note consolidates the compiler analogy so implementers have a stable,
shared mental model for scoping, tool resolution, and recursion.

## Findings

### Mapping: llm-do to compiler/runtime concepts

| llm-do concept | Compiler/runtime analogy | Why it helps |
| --- | --- | --- |
| EntryRegistry | Global symbol table + linker map | One canonical namespace of entries and toolsets. |
| Worker.toolsets | Import table | Declares the capabilities the worker can resolve. |
| CallFrame.active_toolsets | Runtime import table | Actual toolsets in scope for this call (wrapped for approval). |
| CallFrame.messages | Stack locals | Fresh per call; not inherited; only explicit inputs flow. |
| Runtime/RuntimeConfig | Process globals + constants | Shared usage, approvals, callbacks, max depth. |
| ApprovalToolset | Syscall/capability gate | Effectful calls require permission at the LLM boundary. |
| Project manifest (CLI) | Build config / linker invocation | Declares sources, entry symbol, and runtime flags for a run. |

### Compile/link/run mental model

```
Sources (.agent + .py)
    <- Manifest selects files + entry + runtime config
    -> EntryRegistry (symbol table)
    -> resolve toolset refs (link)
    -> run: CallFrame stack frames
```

- EntryRegistry is built in two passes: discover entries/toolsets, then resolve
  toolset references. Duplicate toolset names are link-time errors.
- Workers imported as tools are wrapped in WorkerToolset adapters. This is the
  "linker shim" that exposes a worker as a callable tool.
- Resolution happens at registry build time, so workers run with a fixed import
  table unless explicitly overridden at runtime.

### Toolsets as import tables

- A worker's `toolsets` list is its import table: the complete allowlist of
  capabilities it can call. Toolsets are not inherited from callers.
- Tool lookup is by name across toolsets, in order. This is import-order
  shadowing: the first toolset that defines a tool name wins. Avoid collisions.
- CallFrame.active_toolsets is the runtime view of the import table. For workers,
  the runtime wraps toolsets with ApprovalToolset before the LLM runs.

### Messages as locals

- Each CallFrame owns its own `messages` list and `prompt`; these are local to
  the call. Parent frames never see child message histories.
- Data flows only through explicit inputs/outputs, like function args and return
  values. If you need history, pass it explicitly as an argument (or seed a run
  with `message_history`).
- Runtime.message_log is a global trace for diagnostics; it is not part of any
  worker's conversational context.

### Tool calls as syscalls (trust boundary)

- Tool calls are syscalls: the ApprovalToolset wrapper decides whether the call
  is permitted. This is a capability gate, not isolation.
- `@entry` functions are trusted code, but their `ctx.call()` usage still flows
  through the same syscall gate for parity and observability. Raw Python is the
  kernel-mode escape hatch (no approvals/events).

### Recursion semantics (now supported)

- Self-recursion is explicit: a worker lists its own name in `toolsets`, which is
  equivalent to importing itself.
- Each recursive call forks a new CallFrame (depth + 1) with fresh locals.
- RuntimeConfig.max_depth is the stack limit. Use explicit depth parameters when
  you want the worker to control its own budget.

### Practical implications for implementers

- Think in terms of link-time scoping, not dynamic discovery: if a capability is
  not in the worker's toolsets, it does not exist for that worker.
- Avoid tool name collisions across toolsets or rely on import ordering if you
  must shadow a tool.
- To keep recursion safe and comprehensible, pass state explicitly rather than
  smuggling it through shared message history.

## Open Questions
- Should tool name collisions across toolsets become link-time errors instead of
  import-order shadowing?
- Do we want explicit namespacing or aliasing in toolsets to reduce ambiguity?
- Should we document a canonical "threaded history" pattern for the rare cases
  that need message history propagation?
- Is max_depth best as a global stack limit, or do we want per-worker budgets?

## Conclusion
Adopt the compiler analogy: EntryRegistry is the symbol table, toolsets are
import tables, CallFrame.messages are locals, and approvals are syscall gates.
This model keeps recursion safe, makes capability scoping explicit, and gives
implementers a time-tested way to reason about llm-do's execution model.
