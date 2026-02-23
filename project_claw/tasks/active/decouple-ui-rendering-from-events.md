# Decouple UI rendering from events

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Make UI events data-only and move all rendering/widget creation into renderer backends so new formats do not require editing every event class.

## Context
- Relevant files/symbols:
  - `llm_do/ui/events.py` defines `UIEvent` subclasses with `render_rich`, `render_text`, `create_widget`.
  - `llm_do/ui/display.py` calls event render methods directly.
  - `llm_do/ui/adapter.py` adapts `RuntimeEvent` -> `UIEvent`; runtime already emits `RuntimeEvent`.
  - `llm_do/ui/app.py`, `llm_do/ui/widgets/*` use event widget creation paths.
- Related tasks/notes/docs (inlined from `docs/notes/reviews/review-solid.md`):
  - UIEvent classes mix data + presentation (`render_rich`, `render_text`, `create_widget`), giving each event multiple reasons to change.
  - Adding a new render format requires edits across every UIEvent subclass.
  - UIEvent mandates render methods even when a backend never uses them (ISP pain).
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Backend-specific renderers (Rich/Text/Textual) using per-event dispatch (singledispatch) and backend render-ops; Textual renderer owns streaming + widget creation.
- Inputs:
  - Current coupling: event classes own data + formatting + widget creation.
  - Goal is to add render formats without touching event classes.
  - Truncation limits should live in renderer config, not on events.
  - No backcompat constraints; favor simpler architecture over preserving old APIs.
- Options:
  - Option A: Backend-specific renderer classes (RichRenderer/TextRenderer/TextualRenderer) with a registry or `functools.singledispatch` for per-event rendering.
  - Option B: Visitor pattern (`UIEvent.accept(renderer)`), keeping event classes minimal but still requiring a method per event.
  - Option C: Two-step conversion (UIEvent -> RenderModel per backend), centralizing formatting and widget assembly separately from events.
- Outcome: Pick Option A; avoid visitor to keep events data-only, avoid render models (YAGNI).
- Follow-ups:
  - Update `docs/ui.md` to explain the new rendering pipeline.
  - Remove dead render helpers from `ui/events.py` after migration.
  - Make `MessageContainer` render-agnostic (renderer handles event dispatch).

## Tasks
- [ ] Inventory existing per-event render behavior and widget creation needs (rich/text/textual + streaming).
- [ ] Define renderer interfaces + render-op data (rich/text/textual).
- [ ] Implement rich/headless renderers and update `ui/display.py` to delegate (no event-specific checks).
- [ ] Implement Textual renderer and move event dispatch out of `MessageContainer`.
- [ ] Refactor `ui/events.py` to pure data classes (no render methods).
- [ ] Update tests for display backends, renderer dispatch, and streaming behavior.
- [ ] Update docs to reflect the new rendering architecture.

## Current State
Decision recorded; UI events still own rendering and widget creation, and display backends still delegate to event methods.

## Notes
- Keep runtime/UI separation intact (runtime emits only `RuntimeEvent`).
- Ensure new render formats can be added without touching every event class.
- Prefer removing obsolete helpers over keeping backcompat shims.
- Tool result truncation for LLMs happens in toolsets (e.g., shell output size, read_file max_chars); UI truncation is display-only.
- Open questions:
  - Keep `worker_tag` as a computed property on events, or compute it in renderers?
