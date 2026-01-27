---
description: Standardizing truncation metadata for tool results
---

# Tool Result Truncation Metadata

## Context
We are decoupling UI rendering from events and revisiting whether tool results
should always expose truncation metadata. Today truncation occurs at multiple
layers: toolsets may truncate outputs for safety, and the UI may truncate for
display. This intersects with the broader rendering semantics discussion in
`docs/notes/tool-output-rendering-semantics.md`.

## Findings
- Toolset-level truncation is real but inconsistent:
  - Shell caps stdout/stderr at `MAX_OUTPUT_BYTES` and sets `ShellResult.truncated`.
  - Filesystem reads cap at `max_chars` and return `ReadResult.truncated` plus
    `total_chars`, `offset`, `chars_read`.
- Runtime events (`ToolResultEvent`) carry tool content as-is; they do not add
  truncation metadata. UI truncation is display-only and can hide tool-level
  truncation cues (suffixes/flags).
- Tool outputs are unconstrained (string/dict/model), so a universal truncation
  field does not exist today.
- Standardization options:
  - Event-level metadata: add optional truncation info to `ToolResultEvent`,
    extracted from known tool result types. Helps UI, but LLM may not see it.
  - Tool-output envelope: wrap tool outputs as `{content, truncation}` so the
    LLM always sees truncation state. Most consistent, but intrusive/breaking.
  - Protocol-based: define a convention (`truncated`, `limit`, `total`,
    `offset`, `units`) and only toolsets that support it provide fields. UI can
    extract when present; avoids breaking changes but not universal.
- Any approach should preserve the distinction between "tool truncated" and
  "display truncated" so the UI can signal both.

## Open Questions
- Does "always" mean LLM-visible truncation metadata, or is UI visibility
  sufficient?
- Is a tool output envelope acceptable, or should we keep tool schemas
  unchanged and use best-effort extraction?
- What minimal metadata is required beyond a boolean, and should it align with
  `ReadResult`/`ShellResult` fields?
- How should UIs surface truncation: badge, suffix, status line, or separate
  event?
- Should renderer-level truncation be disabled or adjusted when tool output
  already declares truncation?

## Conclusion
(pending)
