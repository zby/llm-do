# Simplify runtime/call.py

## Context
Simplification review of `llm_do/runtime/call.py` plus its internal dependency
`llm_do/runtime/contracts.py` to shrink the call-frame surface area and remove
duplicated construction logic.

## Findings
- **CallFrame passthrough properties duplicate the config surface**
  - Pattern: over-specified interface / duplicated derived values.
  - Current code exposes `active_toolsets`, `model`, `depth`, and
    `invocation_name` both on `CallConfig` and `CallFrame`.
  - Simplified version: drop the passthrough properties and access
    `frame.config.<field>` at call sites.
  - Tradeoff: call sites become slightly more verbose, but immutability is
    more explicit and the `CallFrame` API shrinks.

- **CallConfig construction is repeated in multiple places**
  - Pattern: duplicated derived values (tuple normalization, depth increment).
  - Call sites: `Runtime._build_entry_frame`, `CallFrame.fork`, and
    `tests/runtime/helpers.py` all re-create `CallConfig` with similar rules.
  - Simplified version: centralize construction, e.g. a small helper on
    `CallConfig` (`fork()` or `from_toolsets(...)`) and reuse it everywhere.
  - This avoids tuple-normalization drift and makes depth increment logic
    single-source.

- **CallScope exposes a redundant `frame` accessor**
  - Pattern: over-specified interface.
  - `CallScope` already exposes `runtime`, which itself exposes `frame`.
  - Simplified version: drop `CallScope.frame` and update the only caller
    (`llm_do/ui/runner.py`) to use `call_scope.runtime.frame`.
  - This keeps CallScope focused on lifecycle + cleanup instead of state access.

## Open Questions
- Do we want the ergonomics of `CallFrame.model`/`CallFrame.depth`, or is the
  explicit `frame.config` boundary the goal?
- Is `CallConfig` intended to be user-constructed in tests/tools, or can we
  funnel creation through a single helper?

## Conclusion
`runtime/call.py` is already lean. The main simplification levers are reducing
the duplicate config surface on `CallFrame` and centralizing `CallConfig`
construction so tuple normalization and depth increments live in one place.
