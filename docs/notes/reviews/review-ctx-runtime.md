# Ctx Runtime Review

## Context
Review of ctx_runtime core for bugs, inconsistencies, and overengineering.

## Findings
- `llm_do/ctx_runtime/entries.py` references `json` in `_format_prompt` and `mimetypes` in `_load_attachment` without importing either module. Any code path that formats prompts or loads attachments will raise `NameError`, breaking worker runs that include attachments or reuse those helpers for logging.
- The code-entry detection path in `llm_do/ctx_runtime/cli.py` only extracts tool names from `FunctionToolset` (and `WorkerEntry`), returning an empty list for other `AbstractToolset` implementations. Python toolsets that rely on custom `get_tools` implementations without `FunctionToolset` inheritance cannot be used as code entry points or checked for duplicate tool names, which may surprise users and mask conflicts.
- `llm_do/ctx_runtime/entries.py` still ships `_format_prompt`, but the function is unused and would also crash due to the missing `json` import. Keeping unused, broken helpers makes it harder to reason about the currently supported code paths.

## Open Questions
- Should we expand `_get_tool_names` to instantiate a temporary `RunContext` and call `get_tools` so non-`FunctionToolset` toolsets can be used as code entry points and participate in duplicate detection? (Would need to avoid side effects during discovery.)
- Are `_format_prompt` and related helpers still needed, or should we remove them (after adding the missing imports) to reduce dead code risk?

## Conclusion
Documented current issues and open questions; no changes applied yet.
