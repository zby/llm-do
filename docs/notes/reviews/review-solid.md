# SOLID Alignment Review

## Context
Review of SOLID alignment across the codebase sections.

## Findings
- **Ctx runtime core**: `Context` currently mixes tool dispatch, model resolution,
  approval defaults, usage tracking, and UI event emission inside a single type,
  making it difficult to extend one concern (e.g., approval) without touching the
  rest of the orchestration code. The constructor and helpers handle everything
  from selecting models to initializing a shared `list[RunUsage]` and tool
  proxies, suggesting a need to separate policy (approval/model selection) from
  dispatch mechanics.【F:llm_do/runtime/ctx.py†L62-L213】
- **UI system**: `LlmDoApp` owns UI composition, message rendering, approval
  batching, worker lifecycle management, and user input history within a single
  class. The accumulation of stateful responsibilities (queues, tasks, history
  management, and message buffers) makes the app hard to test or swap for another
  presentation layer, indicating Single Responsibility and Dependency Inversion
  pressure.【F:llm_do/ui/app.py†L24-L200】
- **Toolsets**: `FileSystemToolset` conflates approval policy (read/write rules),
  path resolution, and the underlying file I/O primitives. There is no interface
  boundary between policy and execution, so any change in approval semantics or
  storage strategy forces edits to the same class rather than substitutable
  collaborators.【F:llm_do/filesystem_toolset.py†L35-L148】
- **Approval wrappers**: Tool-level approval now uses the bare
  `pydantic_ai_blocking_approval` API, with headless/TUI callbacks and session
  caching extracted into `approval_wrappers.py`. This separates prompting policy
  from tool execution, but approval decisions still span wrapper callbacks and
  toolset-specific `needs_approval` logic, leaving split responsibilities around
  approval policy.【F:llm_do/runtime/approval_wrappers.py†L1-L138】【F:llm_do/filesystem_toolset.py†L50-L137】
- **Config/auth**: OAuth storage keeps credential modeling, persistence, and a
  module-level mutable backend in one place. Callers are forced to rely on global
  state (`_storage_backend`) instead of depending on an injected storage
  interface, reducing substitutability and making the module a chokepoint for
  both data shape and storage policy.【F:llm_do/oauth/storage.py†L13-L163】

## Open Questions
- Should `Context` delegate approval, usage tracking, and UI event emission to
  dedicated collaborators (e.g., approval strategy, usage tracker, event sink) to
  isolate extension points?
- Would extracting UI concerns into composable widgets (input history manager,
  approval workflow controller, worker runner) make the TUI replaceable without
  altering core message rendering?
- Do we want a policy interface for toolsets that separates approval rules from
  file I/O implementations, now that wrapper callbacks handle prompting and
  caching?
- Should OAuth storage use injected backends (per-call or via context managers)
  rather than a module-level singleton to better align with dependency inversion?

## Conclusion
Multiple areas centralize unrelated responsibilities and rely on global state.
Adopting the bare approval API moved prompting/caching into wrapper callbacks,
but approval policy is still split across wrappers and toolsets, while usage
aggregation remains coupled to `Context`. Segmenting policy from execution (ctx
runtime approvals vs dispatch, toolset approval vs I/O, UI orchestration vs
rendering, OAuth modeling vs persistence) would improve substitutability and
make SOLID-driven refactors safer.
