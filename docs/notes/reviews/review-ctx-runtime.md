# Ctx Runtime Review

## Context
Review of runtime core (`llm_do/runtime/*`) for bugs, inconsistencies, and overengineering.

## Findings
- **schema_in_ref can re-exec modules:** `resolve_schema_ref()` uses `load_module()` directly, which re-imports the module even if it was already loaded by discovery; this can re-run module side effects and produce duplicate class identities. (`llm_do/runtime/schema_refs.py`, `llm_do/runtime/discovery.py`)
- **Max-depth error lacks context:** `Max depth exceeded` does not include worker name or current depth, making cycles harder to debug. (`llm_do/runtime/worker.py`)
- **`runtime.call` resolves tool conflicts by first match:** direct calls iterate toolsets and return the first tool name match, while PydanticAI errors on duplicate tool names. Entry functions can succeed with ambiguous toolsets that would fail for LLM workers. (`llm_do/runtime/deps.py`)
- **Python entry/worker builtins use CWD for `filesystem_project`:** `_get_global_toolsets()` wires `filesystem_project` to `Path.cwd()` rather than a worker/module or manifest root, which diverges from `.worker` semantics and the “worker dir” docs. (`llm_do/runtime/registry.py`, `llm_do/toolsets/builtins.py`)
- **EntryFunction tool calls follow approval policy:** entry code is trusted, but tool calls are wrapped like workers for parity and observability. Keep documentation aligned with this behavior.
- **Message history behavior matches current intent:** top-level runs reuse `message_history`, nested worker calls always start clean (`_should_use_message_history`).

## Open Questions
- Should `runtime.call` enforce tool-name uniqueness (or namespaces) to match worker runs?
- Should Python entries/workers resolve `filesystem_project` relative to module/manifest root instead of CWD?
- Are cyclic worker references intended to work beyond max-depth enforcement? If yes, should cycle detection/error reporting live at resolution or runtime?

## Conclusion
Ctx runtime is stable; main issues are schema-ref re-exec behavior, max-depth error context, and boundary inconsistencies for tool resolution and filesystem base paths. Entry tool-plane parity is aligned; keep docs in sync as the runtime evolves.
