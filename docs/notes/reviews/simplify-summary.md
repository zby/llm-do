# Simplify Summary (2026-02-01)

## Priority Candidates
1) **Remove private PydanticAI message capture and tool-event fallback**
   - `runtime/agent_runner.py` relies on private `_agent_graph` APIs and
     duplicates tool-event parsing. Consolidate to a single event-stream path
     and remove incremental logging plumbing.
2) **Centralize agent-call approval policy**
   - Approval logic is duplicated in `toolsets/agent.py` and
     `toolsets/dynamic_agents.py`. A shared helper would keep policy consistent
     and reduce duplicated config extraction.
3) **Reduce CLI/UI runner duplication**
   - `cli/main.py` and `ui/runner.py` both wire message-log callbacks, entry
     factories, and runtime creation with repeated branching. A shared helper
     (or a single `run_ui` path) would cut repetition.
4) **Consolidate path-ref parsing**
   - `runtime/entry_resolver.py` and `runtime/input_model_refs.py` both parse
     path refs and resolve base paths. A shared helper would reduce drift.

## Cross-Module Themes
- Formatting and rendering logic is duplicated between `ui/events.py` and
  `ui/widgets/messages.py` (tool call/result formatting).
- Many modules use tiny single-purpose helpers that could be inlined or
  grouped to reduce file count.
- Several helpers perform the same validation in multiple layers (manifest
  vs registry, approval rules across toolsets).

## Scope Gaps / Stale Items
- `runtime/event_parser.py` is referenced in the simplify scope but does not
  exist in the tree.
- `docs/notes/reviews/simplify-runtime-worker.md` references
  `runtime/worker.py`, which no longer exists. Consider archiving or updating.
