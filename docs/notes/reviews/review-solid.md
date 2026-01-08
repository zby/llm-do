# SOLID Alignment Review

## Context
Periodic review of SOLID alignment across the core runtime (`llm_do/runtime`),
toolsets (`llm_do/toolsets`), and the UI event/rendering stack (`llm_do/ui`).

## Findings
- **Single Responsibility pressure in runtime**: `WorkerRuntime` and `Runtime`
  handle execution state, tool dispatch, message accumulation, and UI event
  emission, giving them multiple reasons to change across runtime and UI needs.
  (`llm_do/runtime/deps.py`, `llm_do/runtime/shared.py`)
- **Single Responsibility pressure in workers**: `Worker` owns input coercion,
  attachment I/O, agent construction, streaming/non-streaming execution,
  UI event parsing/emission, and message-history updates.
  (`llm_do/runtime/worker.py`, `llm_do/runtime/input_utils.py`,
  `llm_do/ui/parser.py`)
- **Dependency Inversion leak (runtime → UI)**: core runtime contracts and
  execution paths import `UIEvent` types and emit them directly, tying runtime
  logic to UI concepts and rendering dependencies.
  (`llm_do/runtime/contracts.py`, `llm_do/runtime/deps.py`,
  `llm_do/runtime/shared.py`, `llm_do/runtime/worker.py`)
- **Interface Segregation / Open-Closed friction in UI events**: `UIEvent`
  requires render methods for Rich, text, JSON, and Textual widgets; adding a
  new rendering target requires edits across the event hierarchy instead of
  extending a renderer layer. (`llm_do/ui/events.py`, `llm_do/ui/display.py`)
- **Liskov / Interface Segregation smell in toolsets**: `Worker` is an
  `AbstractToolset` but assumes `run_ctx.deps` exposes runtime-specific members
  (`config`, `frame`), so it is not substitutable in arbitrary toolset contexts.
  (`llm_do/runtime/worker.py`, `llm_do/runtime/contracts.py`)
- **Positive moves**: `CallFrame`/`RuntimeConfig` separation keeps config vs
  per-call state clean, toolset creation is centralized, and UI controllers are
  narrowly focused. (`llm_do/runtime/call.py`, `llm_do/toolsets/loader.py`,
  `llm_do/ui/controllers/*`)

## Open Questions
- Should runtime emit data-only events (or a lightweight runtime event protocol)
  and let UI backends translate them, so runtime no longer imports `llm_do/ui/*`?
- Should `WorkerRuntime` delegate dispatch + event emission to collaborators
  (dispatcher, event sink) to reduce responsibility surface?
- Should `Worker` be split into input handling, agent runner, and history/stream
  policy helpers to make LLM execution more modular?
- Should UI rendering move to per-backend renderers (strategy/visitor) instead
  of methods on each `UIEvent` to avoid widespread edits?
- Should the toolset contract (or a `WorkerRuntimeProtocol`) explicitly express
  runtime dependencies so workers are substitutable in other contexts?

## Conclusion
SOLID alignment remains strongest in the UI controllers and toolset builder,
but runtime/event coupling still concentrates responsibilities and keeps
dependencies pointing toward the UI layer. The next leverage point is
decoupling runtime events from UI rendering and extracting worker execution
concerns (input prep, streaming, history policy) into collaborators.
