# SOLID Alignment Review

## Context
Periodic review of SOLID alignment across the core runtime (`llm_do/runtime`),
toolsets (`llm_do/toolsets`), and the UI event/rendering stack (`llm_do/ui`).

## Findings
- **Single Responsibility pressure in runtime**: `WorkerRuntime` owns model
  resolution, tool discovery/dispatch, usage aggregation, message-history state,
  and UI event emission for code-entry tool calls, giving it multiple reasons to
  change. (`llm_do/runtime/deps.py`)
- **Single Responsibility pressure in workers**: `Worker` mixes prompt/attachment
  building, agent construction, streaming/non-streaming execution paths, UI event
  parsing/emission, and message-history updates. (`llm_do/runtime/worker.py`,
  `llm_do/ui/parser.py`)
- **Dependency Inversion leak (runtime → UI)**: runtime contracts and execution
  paths depend on `UIEvent` types and emit them directly, tying core runtime
  logic to UI concepts and Rich/Textual rendering. (`llm_do/runtime/contracts.py`,
  `llm_do/runtime/runner.py`, `llm_do/runtime/deps.py`, `llm_do/runtime/worker.py`,
  `llm_do/ui/events.py`)
- **Open/Closed tradeoff in event model**: `UIEvent` owns rendering for Rich,
  text, JSON, and Textual widgets; adding a new rendering target requires editing
  the base class and every event rather than extending a renderer layer.
  (`llm_do/ui/events.py`, `llm_do/ui/display.py`)
- **Interface Segregation / Liskov smell in tool dispatch**: `WorkerRuntime.call()`
  special-cases workers via `kind` strings and `schema_in`, indicating the
  dispatcher needs capabilities not expressed by `AbstractToolset` and that not
  all toolsets are treated uniformly. (`llm_do/runtime/deps.py`,
  `llm_do/runtime/input_utils.py`, `llm_do/runtime/worker.py`)
- **Positive moves**: UI state is decomposed into small controllers (approval
  queue, input history, worker runner), and toolset configuration avoids mutating
  shared toolset instances via `ToolsetRef`. (`llm_do/ui/controllers/*`,
  `llm_do/toolsets/loader.py`)

## Open Questions
- Should we move to data-only runtime events (e.g., `llm_do/runtime/events.py`)
  and have UI backends render them, so runtime no longer imports `llm_do/ui/*`?
- Should `WorkerRuntime` delegate tool resolution/dispatch and event emission to
  collaborators (dispatcher, event sink) to narrow its responsibility?
- Should the worker/toolset distinction be expressed as a protocol (capabilities)
  instead of `kind` strings and `schema_in` checks?
- Should worker streaming and message-history policy be extracted into a
  runner/helper to keep `Worker` closer to "build Agent + run"?
- Should UI event rendering move to per-backend renderers (strategy/visitor)
  to avoid editing every event when adding a new output format?

## Conclusion
SOLID alignment is still strongest in the UI controllers and toolset builder,
but runtime/event coupling keeps responsibilities concentrated and dependencies
pointing toward the UI layer. The next leverage point remains separating core
runtime events/dispatch from UI rendering and extracting worker execution
concerns (prompt building, streaming, history policy) into collaborators.
