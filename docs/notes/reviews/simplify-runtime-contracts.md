# Simplify runtime/contracts.py

## Context
Simplification review of `llm_do/runtime/contracts.py` plus internal
dependencies used by the contract types (`runtime/approval.py`,
`runtime/args.py`, `runtime/call.py`, `runtime/shared.py`,
`toolsets/loader.py`, `runtime/events.py`).

## Findings
- **WorkerRuntimeProtocol duplicates config/frame surface**
  - Pattern: over-specified interface / duplicated derived values.
  - Current protocol exposes `project_root`, `depth`, `max_depth`, `model`,
    `prompt`, `messages`, `on_event`, `verbosity`, `return_permission_errors`,
    and `approval_callback` in addition to `config` and `frame`.
  - Simplified version: keep `config`, `frame`, `log_messages`, and
    `spawn_child` only; read depth/prompt/messages from `frame` and runtime
    settings from `config`.
  - Follow-up: remove pass-through properties from `WorkerRuntime` so the
    runtime surface matches the protocol and doesn’t drift.

- **WorkerRuntime pass-throughs create two sources of truth**
  - Pattern: duplicated derived values.
  - `WorkerRuntime.project_root` and `return_permission_errors` mirror
    `RuntimeConfig`, while `depth`, `prompt`, and `messages` mirror `CallFrame`.
  - Simplified version: either pick a minimal, explicit set of convenience
    accessors or route all call sites through `config` and `frame`.
  - Tradeoff: call sites get more verbose, but it becomes harder to diverge
    from the canonical state in `RuntimeConfig`/`CallFrame`.

- **Contracts module carries type aliases that aren’t part of the protocol**
  - Pattern: over-specified interface.
  - `EventCallback` and `MessageLogCallback` exist to support
    `RuntimeConfig`/UI, not the protocol itself.
  - Simplified version: move the aliases to `runtime/shared.py` (or
    `runtime/events.py`) to keep `contracts.py` focused on protocol types.
  - Tradeoff: check for import cycles before moving.

## Open Questions
- Is `WorkerRuntimeProtocol` meant to be a minimal PydanticAI deps surface, or a
  convenience-rich API for tool authors?
- If we shrink the protocol, should we also remove `WorkerRuntime` convenience
  properties to prevent tools from relying on them?
- Should `EventCallback`/`MessageLogCallback` live with `RuntimeConfig` instead
  of `contracts.py`, or does centralizing them here outweigh the extra surface?

## Conclusion
The primary simplification lever is shrinking the `WorkerRuntimeProtocol` (and
matching `WorkerRuntime`) to `config` + `frame` so depth/prompt/settings aren’t
duplicated across the API. Secondary cleanup is optional type-alias placement.
