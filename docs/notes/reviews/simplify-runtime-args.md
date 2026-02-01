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
