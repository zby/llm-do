---
description: Periodic review findings for the runtime core.
---

# Ctx Runtime Review

## Context
Review of runtime core (`llm_do/runtime/*`) for bugs, inconsistencies, and overengineering.

## Findings
- **input_model_ref can double-import modules:** `_load_model_module()` falls back to `importlib.import_module` for dotted refs; if the same file was already loaded via `load_module` during discovery, this creates a second module instance (side effects, class identity drift). (`llm_do/runtime/input_model_refs.py`, `llm_do/runtime/discovery.py`)
- **Max-depth error lacks context:** `call_agent` raises `RuntimeError("max_depth exceeded")` without worker name/current depth or max depth, making recursion/cycle debugging harder. (`llm_do/runtime/context.py`)
- **Message-log "JSONL" is multi-line:** `_make_message_log_callback` writes indented JSON, producing multi-line records that break JSONL consumers. (`llm_do/cli/main.py`)
- **Docs claim top-level message_history is consumed, but runtime doesn't pass it to entry agents:** `run_entry` only stores history on the frame, and `call_agent` doesn't forward it; tests enforce this behavior. Align docs or behavior. (`llm_do/runtime/runtime.py`, `llm_do/runtime/context.py`, `docs/reference.md`)

## Open Questions
- Should schema refs prefer path-based loading (or reuse cached modules) even for dotted module refs to avoid duplicate imports?
- Should message_history be plumbed into the entry agent now (depth 0), or should docs be explicit that chat history is UI-only for now?

## Conclusion
Ctx runtime is stable; remaining issues are schema-ref double-import risk, max-depth error context, JSONL logging format, and message_history documentation mismatch.

## Review 2026-01-27

### Scope Notes
- `llm_do/runtime/worker_file.py` and `llm_do/runtime/toolsets.py` no longer exist; current equivalents appear to be `llm_do/runtime/agent_file.py` and `llm_do/toolsets/`.

### Findings
- **Docs still claim `message_history` is consumed at depth 0, but entry agents ignore it:** `Runtime.run_entry` only seeds `CallFrame.messages`; `call_agent` never forwards history to `run_agent`, and tests assert history is ignored across turns. Update docs or implement history pass-through. (`llm_do/runtime/runtime.py`, `llm_do/runtime/context.py`, `docs/reference.md`, `tests/runtime/test_message_history.py`)
- **Schema refs can still double-import modules:** `resolve_input_model_ref` uses `importlib.import_module` for dotted refs, which can load a second module instance when the same file was already loaded via path-based discovery. This risks side effects and class identity mismatches. (`llm_do/runtime/input_model_refs.py`, `llm_do/runtime/discovery.py`)

### Resolved Since Prior Review
- **Max-depth errors now include context:** `call_agent` reports depth/max/caller/attempted in the exception message. (`llm_do/runtime/context.py`)
- **Message-log JSONL is now single-line:** `_make_message_log_callback` emits compact JSON per record. (`llm_do/cli/main.py`)

### Open Questions
- Should entry agents start receiving `message_history` (depth 0), or should docs state history is UI-only until runtime owns sync?
- Should schema ref resolution reuse the discovery cache for dotted module refs, or should docs steer users to path-based schema refs to avoid duplicate imports?

## Review 2026-02-01

### Findings
- **`allow_cli_input` does not guard stdin:** the CLI only checks prompt/`--input-json`; piped stdin is still accepted even when the manifest sets `allow_cli_input=false`. (`llm_do/cli/main.py`, `llm_do/runtime/manifest.py`)
- **Message history still not plumbed to entry agents:** `Runtime.run_entry` seeds `CallFrame.messages`, but `call_agent` never forwards history into `run_agent`; chat turns remain stateless. (`llm_do/runtime/runtime.py`, `llm_do/runtime/context.py`, `llm_do/runtime/agent_runner.py`, `llm_do/ui/runner.py`)
- **Module discovery cache never invalidates:** `load_module` caches by resolved path and never reloads, which can surprise long-lived sessions that expect file edits to take effect. (`llm_do/runtime/discovery.py`)

### Open Questions
- Should stdin be treated as CLI input and blocked when `allow_cli_input=false`?
- Should runtime own message_history and pass it to depth-0 agents?
- Do we want a cache-busting path (or opt-out) for `load_module` in dev workflows?
