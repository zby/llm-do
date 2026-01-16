# Simplify runtime/deps.py

## Context
Simplification review of `llm_do/runtime/deps.py` and its internal dependencies
(`runtime/approval.py`, `runtime/args.py`, `runtime/call.py`,
`runtime/contracts.py`, `runtime/events.py`, `runtime/shared.py`,
`runtime/worker.py`, `toolsets/validators.py`) to reduce duplicated surface
area in `WorkerRuntime`, simplify tool-call validation, and remove unused
conveniences.

## Findings
- **WorkerRuntime pass-through properties mirror config/frame** ✅ DONE
  - Pattern: over-specified interface / duplicated derived values.
  - The runtime previously exposed `project_root`, `approval_callback`,
    `return_permission_errors`, `max_depth`, `on_event`, `verbosity`, `prompt`,
    `messages`, `depth`, `model`, `active_toolsets`, `usage`, and `message_log`
    as pass-throughs to `RuntimeConfig` or `CallFrame`.
  - Resolution: pass-throughs removed. WorkerRuntime now exposes only `runtime`,
    `frame`, `config` (shortcut to `runtime.config`), `spawn_child`, `call`,
    `log_messages`, and internal helpers. Call sites use `deps.config.*` and
    `deps.frame.*` for state access.

- **ToolsProxy is unused outside tests** ✅ DONE
  - Pattern: unused flexibility.
  - Resolution: removed `ToolsProxy` class, `WorkerRuntime.tools` attribute,
    and export from `__init__.py`. Tests now use `ctx.call(name, args)` directly.

- **_validate_tool_args duplicates WorkerArgs normalization** ✅ DONE
  - Pattern: redundant validation / duplicate derived values.
  - Resolution: removed WorkerToolset special-case from `_validate_tool_args`.
    Worker._call_internal handles normalization via `ensure_worker_args`.

- **_make_run_context parameters are redundant** ✅ DONE
  - Pattern: redundant parameters / over-specified interface.
  - Resolution: simplified to `_make_run_context(self, tool_name: str)`. Uses
    `self.frame.model` and `self` internally. Call sites now just pass the
    tool name.

- **call() does two passes over toolsets** ✅ DONE
  - Pattern: duplicated derived values.
  - Resolution: now collects tool names into `available` list during the search
    loop and reuses it for the error message. Single pass over toolsets.

- **usage/message_log accessors are unused** ✅ DONE
  - Pattern: unused flexibility / over-specified interface.
  - Resolution: `WorkerRuntime.usage` and `WorkerRuntime.message_log` properties
    removed. Internal code reads from `runtime` directly where needed.

## Open Questions
- Should `WorkerRuntime` be a minimal deps surface (`config` + `frame`) or a
  convenience-heavy API for tools?
- Is `ctx.tools.<name>` a supported public affordance, or just test sugar?
- Should `ModelType` be resolved to a concrete `Model` once per frame to avoid
  repeated `infer_model` calls, or is lazy resolution still preferred?

## Conclusion
All simplifications complete. `WorkerRuntime` now has a minimal surface area:
`runtime`, `frame`, `config`, `spawn_child`, `call`, `log_messages`, and
internal helpers only. Removed unused conveniences (`ToolsProxy`, pass-through
properties) and eliminated duplicate validation/lookup passes.
