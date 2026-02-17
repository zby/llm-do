---
_schema:
  entity_type: "observation"
  applies_to: "ops/observations/*.md"
  required:
    - description
    - category
    - observed
    - status
  enums:
    category:
      - methodology
      - process
      - friction
      - surprise
      - quality
    status:
      - pending
      - promoted
      - implemented
      - archived
  constraints:
    description:
      max_length: 200
      format: "What was observed"

# Template fields
description: ""
category: ""
observed: ""
status: pending
---

# {what was observed — prose sentence}

{Details of the observation, context, and potential implications}

---

Topics:
- [[methodology]]
