# Simplify Summary (2026-02-01)

## Priority Candidates
1) **Reduce CLI/UI runner duplication**
   - `cli/main.py` and `ui/runner.py` both wire message-log callbacks, entry
     factories, and runtime creation with repeated branching. A shared helper
     (or a single `run_ui` path) would cut repetition. Render loop wiring is
     now shared; remaining duplication is mostly in CLI branching.

## Cross-Module Themes
- Formatting and rendering logic is duplicated between `ui/events.py` and
  `ui/widgets/messages.py` (tool call/result formatting).
- Many modules use tiny single-purpose helpers that could be inlined or
  grouped to reduce file count.
- Several helpers perform the same validation in multiple layers (manifest
  vs registry, approval rules across toolsets).

## Scope Gaps / Stale Items
- None currently; stale worker-era notes and missing modules have been removed.

## Simplify Summary (2026-02-09)

## Priority Candidates
1) **Unify project/discovery + runtime/toolset validation wrappers**
   - `project/discovery.py`, `project/tool_resolution.py`, and `runtime/call.py` each implement parallel callable/toolset validation and registry-name tagging patterns.
   - A shared resolver/validator layer would remove duplicated runtime checks and reduce drift.
2) **Collapse UI rendering duplication**
   - `ui/events.py` and `ui/widgets/messages.py` still both implement tool call/result formatting and truncation.
   - Keep one formatter source and let render targets reuse it.
3) **Split large orchestration methods (`ui/runner.py`, `project/registry.py`, `toolsets/dynamic_agents.py`)**
   - These modules mix validation, IO, wiring, and error shaping in single methods.
   - Small staged helpers would improve readability without changing behavior.

## Cross-Module Themes
- Duplicated validation wrappers (tool/toolset return-type checks, approval-mode branching).
- Overwide interfaces with pass-through properties and long argument lists.
- Compatibility shims that can be retired (`toolsets/loader.py`, thin proxy modules).

## Scope Gaps / Stale Items
- Runbook mapping now uses `simplify-project-*.md` and `simplify-runtime-tooling.md`; these notes were created in this run to align output paths.
- Legacy `simplify-runtime-{agent-file,discovery,entry-resolver,input-model-refs,manifest,registry}.md` files remain as historical records and can be archived once references are updated.
