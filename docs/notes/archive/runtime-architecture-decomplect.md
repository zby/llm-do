# Runtime architecture decomplect review

## Context
Requested decomplect-py analysis on core runtime and UI modules. Capture high-level design trade-offs and potential refactor targets without committing to implementation.

## Findings
- System model: entry resolution (two-pass registry) -> runtime config -> call frame -> worker agent run -> event stream -> UI adapters.
- Simplicity: CallConfig/CallFrame and PromptSpec separate immutable config from mutable state. However Worker centralizes I/O, eventing, toolset lifecycle, model selection, and message history; changes in any axis touch the same class.
- FCIS: Several pure-ish slices are testable (event_parser, formatting, manifest parsing, model selection). Worker.run_turn mixes domain logic with I/O and agent execution; a single seam for injection is missing.
- Coupling: WorkerToolset in toolsets/loader links runtime and toolset layers; local import hints at a cycle. Approval policy spans runtime/approval, toolsets/approval, toolset implementations, and WorkerToolset; policy semantics are implicit.
- Stability risk: dependence on pydantic_ai internal _agent_graph for message capture may break across upstream versions.

## Open Questions
- Should Worker be split into an "execution core" and "orchestration shell," or is the single class a deliberate simplicity trade?
- Is the two-pass registry the right abstraction, or should linking be explicit to avoid partially resolved objects?
- Does approval policy need a single authoritative surface, or is distributed configuration acceptable?
- Should internal message capture have a fallback or wrapper to reduce coupling to private APIs?
