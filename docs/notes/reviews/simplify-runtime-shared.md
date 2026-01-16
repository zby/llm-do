# Simplify Runtime Shared

## Context
Simplification review of the runtime entrypoint in `llm_do/runtime/shared.py`
(`Runtime.run_entry`) with support from `runtime/approval.py`,
`runtime/args.py`, `runtime/call.py`, `runtime/contracts.py`,
`runtime/events.py`, and `runtime/worker.py`.

## Findings
- **Target module removed (`runtime/runner.py`) DONE**
  - Pattern: unused wrapper removed.
  - Runtime entrypoint now `Runtime.run_entry` in `llm_do/runtime/shared.py`.
  - Recurring task renamed to match.

- **`Runtime.run_entry` checks `Worker.model` for None even though
  `Worker.__post_init__` selects a model or raises**
  - Pattern: redundant validation.
  - Simplify by dropping the `if invocable.model is None` guard if `Worker`
    instances are treated as immutable after init.
  - Caveat: keep the guard if callers can mutate `worker.model = None`.

- **EntryFunction/Worker branches duplicate frame + event setup**
  - Pattern: duplicated derived values / over-specified interface.
  - Both branches set `frame.prompt`, construct `WorkerRuntime`, and emit
    `UserMessageEvent`.
  - Consider a small helper to build the context and emit the event to avoid
    drift.

## Open Questions
- Do we consider `Worker.model` immutable after `__post_init__`, allowing
  removal of the None check?

## Conclusion
`runtime/runner.py` is already removed and prior simplifications appear
implemented. Remaining opportunities are minor: remove the redundant
`Worker.model` check (if safe) and optionally consolidate the duplicated setup
between entry branches.
