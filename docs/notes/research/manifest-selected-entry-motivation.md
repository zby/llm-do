---
description: Motivation for moving entry selection from worker to manifest
---

# Manifest-Selected Entry Motivation

## Context
We discussed moving entry selection out of `.worker` frontmatter and into the
project manifest. The motivation is to simplify the worker file format so it
resembles a generic PydanticAI agent specification, and to centralize
run-level decisions (like which entry to invoke) in the manifest.

## Findings
- The `entry: true` frontmatter flag is entry-selection metadata, not an agent
  configuration concern. Keeping it in `.worker` files makes workers less
  generic and introduces a special-case field that PydanticAI agent specs do
  not otherwise need.
- Manifest-level entry selection aligns with the "build config / linker
  invocation" model (manifest chooses the entry symbol), and it enables
  multiple entry candidates within the same file set without requiring edits
  to worker files.
- This approach makes workers cleaner and more portable as specs, but it shifts
  "runnable as entry" from the worker itself to the surrounding project
  configuration. That is a deliberate tradeoff.

## Open Questions
- Should `entry.name` be required in all manifests, even when there is only one
  candidate?
- How should direct `.worker` execution (if supported later) infer or supply
  `entry.name` without reintroducing frontmatter flags?
- Should `entry` in worker frontmatter become a hard error to prevent silent
  confusion?
- What are the exact conflict rules if a worker and a Python `EntrySpec` share
  the same name?

## Conclusion
