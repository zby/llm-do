---
description: Semantic render hints for structured tool output display
---

# Tool Output Rendering Semantics

## Context
The TUI currently renders assistant/tool output as plain text to avoid markup
injection and to match headless output. This limits formatting and makes large
tool payloads hard to read. We need a forward-looking way for toolsets to
provide structured, safe render hints (semantic types) without embedding markup.

## Findings
- Literal text is the safest default and keeps headless/TUI parity.
- Tool call/result formatting and truncation should be consistent across
  backends to avoid surprises.
- Any richer UI should be driven by explicit semantics, not raw markup strings,
  to avoid unsafe rendering and cross-backend divergence.

## Open Questions
- What minimal schema should toolsets expose for rendering? Examples: structured
  payloads with a `render_kind`, `summary`, `details`, or rich metadata.
- Should render hints be attached to tool outputs (result envelopes) or to
  tool definitions (schema-level metadata)?
- How do we keep headless output faithful while allowing richer TUI widgets?
- Do we need a common truncation policy that toolsets can override?

## Conclusion
(pending)
