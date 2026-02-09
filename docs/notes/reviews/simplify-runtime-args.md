# Simplify: runtime/args.py

## Context
Review of prompt/message helpers and AgentArgs normalization.

## Findings
- `_normalize_text()` and `get_display_text()` both implement the same
  "(no input)" fallback. Consolidate to one helper to avoid drift.
- `render_prompt()` and `get_display_text()` each rebuild text rendering from
  `PromptMessages`. Consider a single `PromptMessages` helper that returns
  `(display_text, rendered_prompt)` to reduce repeated traversal.
- `Attachment.render()` resolves paths; other components (e.g., toolsets) also
  normalize paths. Choose a single normalization point to avoid duplicate
  path resolution.

## Open Questions
- Should `normalize_input()` accept generic Pydantic `BaseModel` inputs and
  coerce them into `AgentArgs`, or is the explicit `AgentArgs` contract
  important for safety?

## 2026-02-09 Review
- `render_prompt()` and `get_display_text()` both walk `PromptMessages`; a single pass helper returning `(display_text, rendered_prompt)` would remove duplicate traversal.
- `normalize_input()` enforces exact `AgentArgs` subtype equality for instances (`type(input_data) is not input_model`), which adds strictness and branch complexity; consider `isinstance` unless exact-type matching is required.
- `_normalize_text()` fallback logic is still repeated across render/display paths and can be centralized.
