# Simplify Summary (2026-02-01)

## Priority Candidates
1) **Reduce CLI/UI runner duplication**
   - `cli/main.py` and `ui/runner.py` both wire message-log callbacks, entry
     factories, and runtime creation with repeated branching. A shared helper
     (or a single `run_ui` path) would cut repetition. Render loop wiring is
     now shared; remaining duplication is mostly in CLI branching.
2) **Consolidate path-ref parsing**
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
