# Ctx Runtime Review

## Context
Review of runtime core (`llm_do/runtime/*`) for bugs, inconsistencies, and overengineering.

## Findings
- **schema_in_ref can double-import modules:** `_load_schema_module()` falls back to `importlib.import_module` for dotted refs; if the same file was already loaded via `load_module` during discovery, this creates a second module instance (side effects, class identity drift). (`llm_do/runtime/schema_refs.py`, `llm_do/runtime/discovery.py`)
- **Max-depth error lacks context:** `call_agent` raises `RuntimeError("max_depth exceeded")` without worker name/current depth or max depth, making recursion/cycle debugging harder. (`llm_do/runtime/deps.py`)
- **Message-log "JSONL" is multi-line:** `_make_message_log_callback` writes indented JSON, producing multi-line records that break JSONL consumers. (`llm_do/cli/main.py`)
- **Docs claim top-level message_history is consumed, but runtime doesn't pass it to entry agents:** `run_entry` only stores history on the frame, and `call_agent` doesn't forward it; tests enforce this behavior. Align docs or behavior. (`llm_do/runtime/shared.py`, `llm_do/runtime/deps.py`, `docs/reference.md`)

## Open Questions
- Should schema refs prefer path-based loading (or reuse cached modules) even for dotted module refs to avoid duplicate imports?
- Should message_history be plumbed into the entry agent now (depth 0), or should docs be explicit that chat history is UI-only for now?

## Conclusion
Ctx runtime is stable; remaining issues are schema-ref double-import risk, max-depth error context, JSONL logging format, and message_history documentation mismatch.
