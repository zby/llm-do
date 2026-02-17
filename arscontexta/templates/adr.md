---
_schema:
  entity_type: "adr"
  applies_to: "docs/adr/*.md"
  required:
    - description
  optional:
    - areas
    - status
    - supersedes
  enums:
    status:
      - proposed
      - accepted
      - superseded
      - deprecated
  constraints:
    description:
      max_length: 200
      format: "One sentence summarizing the decision"
    areas:
      format: "Array of wiki links to area indexes"

# Template fields
description: ""
areas: []
status: accepted
---

# {NNN}-{decision-title}

## Status

{proposed | accepted | superseded | deprecated}

## Context

{What is the issue that motivates this decision?}

## Decision

{What is the change being proposed/accepted?}

## Consequences

{What becomes easier or harder as a result?}

---

Relevant Notes:
- [[related-note]] — background exploration or research

Topics:
- [[relevant-index]]
