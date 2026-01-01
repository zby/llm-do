# SOLID Alignment Review

## Context
Periodic review of SOLID alignment across the core runtime (`llm_do/runtime`),
toolsets (`llm_do/toolsets`), and the UI event/rendering stack (`llm_do/ui`).

## Findings
- **Single Responsibility pressure in runtime**: `WorkerRuntime` owns model
  resolution, tool discovery/dispatch, usage aggregation, and UI event emission
  for code-entry tool calls, giving it multiple reasons to change.
  (`llm_do/runtime/context.py`)
- **Single Responsibility pressure in workers**: `Worker` mixes prompt/attachment
  building, agent construction, message-history policy, streaming, and UI event
  parsing/emission. (`llm_do/runtime/worker.py`, `llm_do/ui/parser.py`)
- **Dependency Inversion leak (runtime → UI)**: the runtime layer depends on
  `UIEvent` types and emits them directly, tying the "core" runtime to UI
  concepts and (indirectly) to Rich/Textual rendering. (`llm_do/runtime/contracts.py`,
  `llm_do/runtime/runner.py`, `llm_do/runtime/context.py`, `llm_do/runtime/worker.py`,
  `llm_do/ui/events.py`)
- **Open/Closed tradeoff in event model**: `UIEvent` owns rendering for Rich,
  text, JSON, and Textual widgets; adding a new rendering target or changing
  formatting requires editing many event classes instead of extending via new
  renderer implementations. (`llm_do/ui/events.py`, `llm_do/ui/display.py`)
- **Interface Segregation / Liskov smell in tool dispatch**: `WorkerRuntime.call()`
  special-cases workers via a string `kind` and `schema_in`, indicating the
  dispatcher needs capabilities not expressed by `AbstractToolset` and that not
  all toolsets are treated uniformly. (`llm_do/runtime/context.py`,
  `llm_do/runtime/input_utils.py`, `llm_do/runtime/worker.py`)
- **Positive moves**: the TUI is decomposed into small controllers (approval
  queue, input history, worker runner), and OAuth storage uses an injected
  backend rather than module-level state. (`llm_do/ui/controllers/*`,
  `llm_do/oauth/storage.py`)
- **Possible duplication**: both `llm_do/toolsets/builtins.py` and
  `llm_do/toolsets/loader.py` provide built-in resolution paths, but only the
  loader appears to be used by the CLI, suggesting a cleanup opportunity.
  (`llm_do/toolsets/builtins.py`, `llm_do/toolsets/loader.py`, `llm_do/runtime/__init__.py`)

## Open Questions
- Should we move to data-only runtime events (e.g., `llm_do/runtime/events.py`)
  and have UI backends render them, so runtime no longer imports `llm_do/ui/*`?
- Should `WorkerRuntime` delegate tool resolution/dispatch and event emission to
  collaborators (dispatcher, event sink) to narrow its responsibility?
- Should the worker/toolset distinction be expressed as a protocol (capabilities)
  instead of `kind` strings and `getattr` checks?
- Should worker streaming and message-history policy be extracted into a
  runner/helper to keep `Worker` closer to "build Agent + run"?
- Is `llm_do/toolsets/builtins.py` still needed now that class-path/alias loading
  exists in `llm_do/toolsets/loader.py`?

## Conclusion
SOLID alignment is improving in UI and OAuth, but runtime/event coupling still
concentrates responsibilities and inverts dependencies. The next leverage point
is separating core runtime events and dispatch from UI rendering and worker-run
orchestration details.
