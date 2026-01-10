# Single Source of Truth for Tool Call Events

## Idea
Unify tool event emission so tool call data (args, args_json) comes from a
single, consistent source across event-stream parsing and message synthesis.
Related analysis: `docs/notes/tool-event-synthesis-single-source-of-truth.md`.

## Why
The current dual-path tool event flow yields inconsistent UI/JSONL output and
breaks the single source of truth rule. Consolidation should reduce ambiguity,
improve observability, and make debugging tool calls deterministic.

## Rough Scope
- Decide canonical source (event stream vs message history) or define a shared
  normalization layer used by all emission paths.
- Normalize tool args consistently (dict vs JSON string) and align UI/JSONL.
- Update affected paths (`llm_do/runtime/worker.py`, `llm_do/ui/parser.py`,
  `llm_do/runtime/deps.py`) and tests.

## Why Not Now
Needs more analysis and design decisions on canonical representation and
streaming UX tradeoffs.

## Trigger to Activate
Agreement on canonical source/representation or a user-visible bug report about
missing/inconsistent tool call output.
