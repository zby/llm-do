---
name: validate
description: Schema validation for KB notes. Checks frontmatter fields, description quality, type/trait enums, link health, and areas-topics consistency against project conventions. Non-blocking — warns but doesn't prevent editing. Triggers on "/validate", "/validate [note]", "/validate all", "/validate recent".
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
context: fork
model: sonnet
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Parse immediately:
- If target contains a note path or name: validate that specific note
- If target is "all" or "notes": validate all `.md` files in `project_claw/notes/` (including subdirectories)
- If target is "recent" or "today": validate notes modified today
- If target is empty: ask which note to validate

**Execute these steps:**

### Step 1: Locate Target Notes

**Single note:** Resolve the path. If just a name, search `project_claw/notes/` for a matching `.md` file.

**Batch ("all"):** Discover all `.md` files in `project_claw/notes/` recursively.

**Recent:** Find notes modified today:
```bash
find project_claw/notes/ -name "*.md" -mtime 0
```

### Step 2: Read Each Target Note

For each note, read the full file. Parse:
- YAML frontmatter (between `---` delimiters)
- All frontmatter fields and their values
- The body content (for link scanning)
- The footer section (for `Topics:` links)

### Step 3: Run All Checks

Run every check below on each note. Each check produces PASS, WARN, FAIL, or INFO.

**START NOW.**

---

## Schema Checks

### FAIL-level Checks (required — blocks validation)

#### 1. Frontmatter Present

| Check | Rule | How to Verify |
|-------|------|---------------|
| Opening delimiter | File starts with `---` on line 1 | Check first line |
| Closing delimiter | A second `---` exists after YAML fields | Scan for closing delimiter |
| Valid YAML | Parses without errors | Check for common YAML errors: unquoted colons in values, mismatched quotes, bad indentation |

A file without valid frontmatter cannot be validated further. Report FAIL and skip remaining checks.

#### 2. Description Exists

| Check | Rule | How to Verify |
|-------|------|---------------|
| `description` field | Must exist in frontmatter | Check for `description:` key |
| Non-empty | Must have a non-empty value | Check that value is not blank, `""`, or `~` |

### WARN-level Checks (quality — does not block)

#### 3. Description Quality

| Check | Rule | How to Verify |
|-------|------|---------------|
| Length | Should be ~50-200 characters | Count characters in description value |
| New information | Must add context beyond the title | Compare description against filename/title — if semantically equivalent, WARN |
| No trailing period | Convention: descriptions don't end with periods | Check last character |

**How to check "adds new info":** Read the title (filename without `.md`, hyphens to spaces). Read the description. If the description merely restates the title using different words, it fails. A good description adds one of:
- **Mechanism** — how or why the claim works
- **Scope** — what boundaries the claim has
- **Implication** — what follows from the claim
- **Context** — where the claim applies

#### 4. Type Valid

| Check | Rule | How to Verify |
|-------|------|---------------|
| Enum value | If `type:` present, must be one of the valid base types | Compare against allowed list |

**Valid base types:** `note`, `spec`, `review`, `index`, `adr`

If the value is not in the list, report the invalid value and list the valid options.

Skip this check if `type:` is absent (it's optional, defaults to `note`).

#### 5. Traits Valid

| Check | Rule | How to Verify |
|-------|------|---------------|
| Enum values | If `traits:` present, every value must be a valid trait | Compare each against allowed list |

**Valid traits:** `has-claim`, `has-comparison`, `has-external-sources`, `has-implementation`

Report each invalid trait individually. Skip if `traits:` is absent.

#### 6. Status Valid

| Check | Rule | How to Verify |
|-------|------|---------------|
| Enum value | If `status:` present, must be one of the valid statuses | Compare against allowed list |

**Valid statuses:** `current`, `speculative`, `outdated`

Skip if `status:` is absent.

#### 7. Composability

| Check | Rule | How to Verify |
|-------|------|---------------|
| Prose fitness | Title works as inline prose: "since [title]..." reads naturally | Read the title as a sentence fragment |
| Not a topic label | Title makes a claim or describes a specific thing, not just a category | Could someone reasonably reference this in a sentence? |

**Topic labels vs claims:**
- "knowledge management" — topic label, WARNS
- "knowledge management requires curation not accumulation" — claim, PASSES
- "context-loading-strategy" — descriptive name for a specific thing, PASSES

#### 8. Link Health

| Check | Rule | How to Verify |
|-------|------|---------------|
| Markdown link targets | Each `[text](./path.md)` target must resolve to an existing file | Extract all markdown links from body, resolve relative to note's directory, check file exists |
| Skip code blocks | Links inside backtick blocks are examples, not real links | Skip links inside single or triple backtick blocks |
| Skip external URLs | Only check relative links, not `http://` or `https://` | Filter out absolute URLs |

**How to verify:** For each relative markdown link, resolve the path relative to the note's directory and check if the target file exists.

#### 9. Areas-Topics Consistency

| Check | Rule | How to Verify |
|-------|------|---------------|
| Areas without Topics | If `areas:` is set in frontmatter, a `Topics:` footer should exist | Scan for `Topics:` section at end of file |
| Topics without Areas | If `Topics:` footer exists, `areas:` should be set | Check frontmatter for `areas:` field |
| Sync suggestion | If mismatch detected, suggest running sync script | Report: `uv run project_claw/scripts/sync_topic_links.py <note-path>` |

This check verifies that the two representations stay in sync. `areas:` is the source of truth; `Topics:` footer is generated from it.

### INFO-level Checks (signals — no action needed)

#### 10. Orphan Check (batch mode only)

| Check | Rule | How to Verify |
|-------|------|---------------|
| Inbound links | Note is referenced by at least one other note | Grep all notes for markdown links pointing to this file |

Only run in batch mode (`/validate all`). A note with no inbound links may be disconnected from the knowledge graph.

```bash
# Check inbound links for a note
grep -r 'note-filename\.md' project_claw/notes/ project_claw/kb-design/ --include="*.md" | grep -v "^project_claw/notes/note-filename.md:"
```

#### 11. Bare Note Type

| Check | Rule | How to Verify |
|-------|------|---------------|
| Unspecified structure | `type: note` with `traits: []` (empty list) | Check both fields |

A bare `note` with no traits is the honest default — but if it persists, it's a signal the note may benefit from type promotion or trait assignment. Report as INFO.

## Output Format (Single Note)

```
=== VALIDATION: note-title.md ===

PASS:
- frontmatter: valid delimiters, well-formed YAML
- description: present, 147 chars, adds mechanism beyond title
- type: "spec" — valid
- composability: title works as prose

WARN:
- description: 38 chars — below recommended minimum of 50
- areas-topics: areas: [kb-design] set but no Topics: footer found
  → Run: uv run project_claw/scripts/sync_topic_links.py project_claw/notes/note-title.md

FAIL:
- (none)

INFO:
- bare note type: type: note with traits: [] — consider if traits apply

Overall: PASS (2 warnings, 1 info)
===
```

If WARN or FAIL items exist, include:

```
### Suggested Fixes
- **description**: Expand to ~50-200 chars — add mechanism, scope, or implication
- **areas-topics**: Run sync script to generate Topics footer from areas field
```

## Batch Mode

When validating all notes or recent notes:

1. Discover target `.md` files
2. Run all schema checks on each note
3. Run orphan check (INFO level) across the full set
4. Produce summary report

**Batch output format:**

```
## Validation Summary

Checked: N notes
- PASS: M (X%)
- WARN: K (Y%)
- FAIL: J (Z%)

### FAIL Items (immediate attention)
| Note | Check | Detail |
|------|-------|--------|
| note-a.md | description | Missing |
| note-b.md | frontmatter | No closing delimiter |

### Top WARN Patterns
- Description quality (short/restates title): N notes
- Areas-Topics mismatch: N notes
- Invalid enum value: N notes

### INFO Signals
- Orphan notes (no inbound links): N notes
- Bare note type: N notes

### Notes Needing Attention
1. note-a.md — 2 FAIL, 1 WARN
2. note-b.md — 1 FAIL, 3 WARN
```

## Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| PASS | Meets requirement fully | None needed |
| WARN | Quality issue or soft violation | Consider fixing |
| FAIL | Required field missing or structural error | Should fix |
| INFO | Informational signal | No action needed |

**FAIL does not block editing.** Validation is a quality check, not a gate. Notes can exist with failures — validation just surfaces what needs attention.

## Critical Constraints

**never:**
- modify any files (this skill is read-only)
- auto-fix issues — only report and suggest
- skip checks because the note "looks fine"
- report PASS without actually running the check
- use wiki-link syntax `[[...]]` — this KB uses standard markdown links

**always:**
- check ALL schema requirements, not a subset
- report specific field values in FAIL/WARN messages (not just "description is weak")
- suggest concrete fixes for every WARN and FAIL
- resolve link paths relative to the note's directory
- handle subdirectories in `project_claw/notes/` (e.g., `research/`, `agent-learnings/`)
