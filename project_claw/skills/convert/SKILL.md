---
name: convert
description: Convert notes between types. Currently supports text→note (add frontmatter with status seedling). Future directions include note→spec/review/adr and demotion back to text. Triggers on "/convert", "/convert [note]".
user-invocable: true
allowed-tools: Read, Edit, Grep, Glob, Bash
context: fork
model: sonnet
argument-hint: "[note] — path or filename in project_claw/notes/. Optional: [note] to [type]"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If target contains just a note name or path: convert text → note
- If target contains "[note] to [type]": convert to the specified type
- If target is empty: ask which note to convert

## Supported conversions

### text → note (current)

The primary conversion. Adds frontmatter to a raw text file, making it structured and connectable.

#### Step 1: Locate and verify

Resolve the target to a file path. If just a name, search `project_claw/notes/` recursively.

Read the file. Verify it has **no frontmatter** (does not start with `---`). If it already has frontmatter, report that it's already structured and stop.

#### Step 2: Understand the content

Read the full file. Identify:
- The core claim or topic (what is this about?)
- Whether the title works as a claim (assertion) or is just a label
- What structural properties the content has (arguments, comparisons, external sources, code)

#### Step 3: Generate frontmatter

Add YAML frontmatter at the top of the file:

```yaml
---
description: [50-200 chars, adds mechanism/scope/implication beyond the title]
type: note
traits: [assign from: has-claim, has-comparison, has-external-sources, has-implementation]
areas: []
status: seedling
---
```

**Rules:**
- `status` is always `seedling` — conversion structures the note but does not endorse it. Human review flips to `current`.
- `description` must add information beyond the title. See [note-types](../../kb-design/note-types.md) for quality criteria.
- `traits` should reflect what the content actually contains. Empty `[]` is valid if none apply.
- `areas` starts as `[]`. If the note clearly belongs to an existing area index, add it and run the sync script:
  ```bash
  uv run project_claw/scripts/sync_topic_links.py <note-path>
  ```
- Do NOT modify the body content. Conversion adds structure, not editorial changes.

#### Step 4: Report

```
=== CONVERTED: filename.md ===

text → note (status: seedling)

description: [the description you wrote]
traits: [list]
areas: [list or empty]

Next steps:
- /connect filename.md — find connections
- /validate filename.md — check quality
- Review and set status: current when endorsed
===
```

### Future conversions (not yet implemented)

These are documented as directions, not working features. If a user requests one, explain it's not implemented yet.

- **note → spec**: add Design/Implementation sections
- **note → review**: add Findings section, date
- **note → adr**: add Context/Decision/Consequences sections
- **any → text**: strip frontmatter, demote to raw capture (for notes that didn't work out)

## Critical Constraints

**Never:**
- Set `status: current` — that requires human review
- Modify body content — only add/change frontmatter
- Convert a text file that already has frontmatter (it's not a text file)
- Write a description that merely restates the title

**Always:**
- Set `status: seedling` for text → note conversions
- Write a description that adds mechanism, scope, or implication
- Report what was done so the user can review
