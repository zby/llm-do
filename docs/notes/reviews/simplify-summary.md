# Simplify Summary (2026-02-01)

## Priority Candidates
1) **Remove tool-event fallback in agent runner**
   - Incremental message capture (private `_agent_graph`) is now removed.
     The remaining complexity is the tool-event fallback that re-parses
     messages instead of relying solely on the event stream.
5) **Fold tiny auth config module**
   - `runtime/auth.py` only defines a `Literal` alias. Consider inlining into a
     larger config module to reduce file count.
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
- None currently; stale worker-era notes and missing modules have been removed.
