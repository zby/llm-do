---
_schema:
  entity_type: "note"
  applies_to: "docs/notes/*.md"
  required:
    - description
  optional:
    - areas
    - status
    - type
    - related_adr
  enums:
    status:
      - current
      - outdated
      - speculative
    type:
      - analysis
      - design
      - review
      - comparison
      - insight
      - spec
      - research
      - index
  constraints:
    description:
      max_length: 200
      format: "One sentence adding context beyond the title"
    areas:
      format: "Array of wiki links to area indexes"

# Template fields
description: ""
type: ""
areas: []
status: current
---

# {prose-as-title — a proposition, not a topic label}

{Content — your analysis, reasoning, or exploration}

## Open Questions

- {Unresolved points worth tracking}

---

Relevant Notes:
- [[related-note]] — how it relates

Topics:
- [[relevant-index]]
