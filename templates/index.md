---
_schema:
  entity_type: "index"
  applies_to: "docs/notes/*-index.md"
  required:
    - description
  optional:
    - areas
  constraints:
    description:
      max_length: 200
      format: "What this index covers"

# Template fields
description: ""
type: moc
---

# {area-name} index

{Brief description of what this area covers in the llm-do project}

## Notes

- [[note-title]] — brief context

## Decisions

- [[NNN-decision-title]] — brief context

## Related Areas

- [[other-index]] — how they connect

---

Topics:
- [[index]]
