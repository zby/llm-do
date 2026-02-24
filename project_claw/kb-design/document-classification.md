---
description: Base types assert verifiable structure (text, note, spec, review, index, adr); traits assert checkable properties; status tracks commitment (seedling vs current) independently of structure
type: spec
areas: [kb-design]
status: current
---

# Document classification

See [document-types-should-be-verifiable](./document-types-should-be-verifiable.md) for the design rationale.

## Base types

Base types are hard structural categories with low ambiguity. A document has exactly one base type.

| Base type | Structural test | Verifiability |
|-----------|----------------|---------------|
| `text` | No frontmatter — raw capture | Always valid |
| `note` | Has frontmatter with description | Check for frontmatter, description field |
| `spec` | Implementation-ready detail; has Design/Implementation sections | Check for sections |
| `review` | Examines specific existing code; has Findings; dated | Check for code refs, date |
| `index` | Primarily navigational links | Check link density |
| `adr` | Architecture decision record; has Context/Decision/Consequences | Check for ADR sections |

`text` is the root type — like `Any` in a gradually typed language. A markdown file with no frontmatter. It represents a thought captured before it has enough shape to structure. The absence of frontmatter *is* the type — no `type: text` field needed.

`note` is the first structured type. It requires frontmatter with at least a `description` field and carries the expectations from WRITING.md ([title-as-claim](../notes/title-as-claim-enables-traversal-as-reasoning.md), description quality, index membership, composability). Notes with the `has-claim` trait use claim titles that serve as premises in reasoning chains; specs and other multi-claim documents use topical titles instead.

## Status

Status tracks **commitment** — whether a note has been reviewed and endorsed. It is orthogonal to base type: a `note` can be structurally complete (has frontmatter, connections, area membership) while still being provisional.

| Status | Meaning |
|--------|---------|
| `seedling` | Provisional — we haven't decided to keep this. May be pruned. |
| `current` | Endorsed — reviewed and accepted into the KB. |
| `speculative` | Exploratory — deliberately kept as open conjecture. |
| `outdated` | Superseded — kept for reference but no longer the active view. |

The initial status is `seedling`, not "draft" — a draft implies commitment to develop it, while a seedling may simply be pruned.

`text` files (no frontmatter) have implicit `status: seedling`. When a `text` file gains frontmatter (is promoted to `note`), its status should be set explicitly. `/connect` promotes structure (`text` → `note`) but preserves provisionality by setting `status: seedling`, not `status: current`. Human review flips the status to `current`.

**Finding seedlings that need review:**
```bash
rg '^status: seedling' project_claw/notes/
```

## Traits

Traits are independently checkable properties. A document can have zero or more traits regardless of its base type. Stored in the `traits` frontmatter field as a list.

| Trait | What it asserts | Verifiability |
|-------|----------------|---------------|
| `has-claim` | Title is an assertion; body argues for it | Requires judgment |
| `has-comparison` | Structured evaluation of alternatives (tables, option lists) | Grep for comparison tables |
| `has-external-sources` | References material outside the project | Grep for URLs/citations |
| `has-implementation` | Contains code sketches or concrete API proposals | Grep for code blocks with API surface |

### What the old flat types become

| Old type | New encoding |
|----------|-------------|
| `design` | `note` (was subject matter, not structure) |
| `insight` | `note` + `has-claim` |
| `analysis` | `note` + `has-comparison` |
| `research` | `note` + `has-external-sources` |
| `comparison` | `note` + `has-comparison` |

## Frontmatter example

```yaml
---
description: Storing an LLM output collapses a distribution to a point
type: note
traits: [has-claim]
areas: [index]
---
```

## Design principles

**Types are fuzzy.** They are assigned by agents and humans, not compilers. The system must tolerate misclassification — nothing breaks if a type or trait is wrong. Types are search aids, not enforcement boundaries.

**Types are verifiable.** Each type and trait asserts a structural property you can check. The question is "what structural property am I asserting?" not "what is this about?" Subject matter belongs in `areas`.

**Types crystallise.** Content can start as `text` (no frontmatter) and get promoted to `note` by adding frontmatter, then to more specific types as structure develops. A `text` file that persists without promotion is a candidate for pruning. This mirrors the crystallisation gradient applied to the KB itself.

**Status is orthogonal to type.** Structure (`text` → `note` → `spec`) and commitment (`seedling` → `current`) are independent axes. A note can be structurally complete and connected while still being a seedling — meaning "we haven't decided to keep this." This avoids conflating "has enough shape to connect" with "has been reviewed and endorsed."

Topics:
- [kb-design](./kb-design.md)
