---
name: seed
description: Add a source file to the processing queue. Checks for duplicates, creates archive folder, moves source from inbox, creates extract task, and updates queue. Triggers on "/seed", "/seed [file]", "queue this for processing".
version: "1.0"
generated_from: "arscontexta-v1.6"
user-invocable: true
context: fork
model: opus
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
argument-hint: "[file] — path to source file to seed for processing"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

The target MUST be a file path. If no target provided, list arscontexta/inbox/ contents and ask which to seed.

### Step 0: Read Vocabulary

Read `arscontexta/ops/derivation-manifest.md` (or fall back to `arscontexta/ops/derivation.md`) for domain vocabulary mapping. All output must use domain-native terms. If neither file exists, use universal terms.

**START NOW.** Seed the source file into the processing queue.

---

## Step 1: Validate Source

Confirm the target file exists. If it does not, check common locations:
- `arscontexta/inbox/{filename}`
- Subdirectories of arscontexta/inbox/

If the file cannot be found, report error and stop:
```
ERROR: Source file not found: {path}
Checked: {locations checked}
```

Read the file to understand:
- **Content type**: what kind of material is this? (research article, documentation, transcript, etc.)
- **Size**: line count (affects chunking decisions in /extract)
- **Format**: markdown, plain text, structured data

## Step 2: Duplicate Detection

Check if this source has already been processed. Two levels of detection:

### 2a. Filename Match

Search the queue file and archive folders for matching source names:

```bash
SOURCE_NAME=$(basename "$FILE" .md | tr ' ' '-' | tr '[:upper:]' '[:lower:]')

# Check queue for existing entry
# Search in arscontexta/ops/queue.yaml, arscontexta/ops/queue/queue.yaml, or arscontexta/ops/queue/queue.json
grep -l "$SOURCE_NAME" arscontexta/ops/queue*.yaml arscontexta/ops/queue/*.yaml arscontexta/ops/queue/*.json 2>/dev/null

# Check archive folders
ls -d arscontexta/ops/queue/archive/*-${SOURCE_NAME}* 2>/dev/null
```

### 2b. Content Similarity (if semantic search available)

If semantic search is available (qmd MCP tools or CLI), check for content overlap:

```
mcp__qmd__search query="claims from {source filename}" limit=5
```

Or via keyword search in the docs/notes/ directory:
```bash
grep -rl "{key terms from source title}" docs/notes/ 2>/dev/null | head -5
```

### 2c. Report Duplicates

If either check finds a match:
- Show what was found (filename match or content overlap)
- Ask: "This source may have been processed before. Proceed anyway? (y/n)"
- If the user declines, stop cleanly
- If the user confirms (or no duplicate found), continue

## Step 3: Classify Input

Based on the content read in Step 1, classify the source to determine how it should be processed:

| Type | Signal | Processing Mode | Downstream Behavior |
|------|--------|----------------|---------------------|
| **Research paper** | Academic structure, findings/methodology sections, literature references | `extract` | Full atomic claim extraction (existing pipeline) |
| **Design proposal** | API design, PR, RFC, spec, external project proposal | `analyze` | One analysis note on impact to our project |
| **Conversation transcript** | Dialog, session log, chat export | `extract` | Extract our own insights (standard pipeline) |
| **Reference/catalog** | API docs, survey, comparison matrix, changelog | `reference` | Archive as reference, minimal extraction |

**Classification signals:**

- **Research paper:** sections like Abstract, Methodology, Findings, Discussion; citations; hypothesis framing
- **Design proposal:** proposes changes to an API or system; describes what ANOTHER project should do; RFC/ADR structure; code examples showing proposed interfaces
- **Conversation transcript:** alternating speakers, timestamps, Q&A format
- **Reference/catalog:** tabular data, enumerated lists of features, API endpoint documentation, comparison grids

**The key question:** "Is this telling us what to think about OUR project, or proposing what ANOTHER project should do?"
- If it's about our project → `extract`
- If it's another project's proposal and we need to assess impact → `analyze`
- If it's reference material we might look up later → `reference`

Record the classification as `processing_mode` in the task file (Step 7).

### Reference Mode Short-Circuit

If `processing_mode: reference`, skip claim numbering (Step 6) and create a simplified task flow:
1. Create archive structure (Step 4) and move source (Step 5) as normal
2. Instead of an extract task file, write a brief reference note directly to `docs/notes/` summarizing what the document contains and when to consult it
3. Add a queue entry with `type: reference, status: done` (no further processing needed)
4. Skip to Step 9 (Report), noting that the source was archived as reference material

## Step 4: Create Archive Structure

Create the archive folder. The date-prefixed folder name ensures uniqueness.

```bash
DATE=$(date -u +"%Y-%m-%d")
SOURCE_BASENAME=$(basename "$FILE" .md | tr ' ' '-' | tr '[:upper:]' '[:lower:]')
ARCHIVE_DIR="arscontexta/ops/queue/archive/${DATE}-${SOURCE_BASENAME}"
mkdir -p "$ARCHIVE_DIR"
```

The archive folder serves two purposes:
1. Permanent home for the source file (moved from inbox)
2. Destination for task files after batch completion (/archive-batch moves them here)

## Step 5: Move Source to Archive

Move the source file from its current location to the archive folder. This is the **claiming step** — once moved, the source is owned by this processing batch.

**inbox sources get moved:**
```bash
if [[ "$FILE" == *"inbox"* ]] || [[ "$FILE" == *"inbox"* ]]; then
  mv "$FILE" "$ARCHIVE_DIR/"
  FINAL_SOURCE="$ARCHIVE_DIR/$(basename "$FILE")"
fi
```

**Sources outside inbox stay in place:**
```bash
# Living docs (like configuration files) stay where they are
# Archive folder is still created for task files
FINAL_SOURCE="$FILE"
```

Use `$FINAL_SOURCE` in the task file — this is the path all downstream phases reference.

**Why move immediately:** All references (task files, notes' Source footers) use the final archived path from the start. No path updates needed later. If it is in inbox, it is unclaimed. Claimed sources live in archive.

## Step 6: Determine Claim Numbering

**Skip this step if `processing_mode: reference`** (reference mode short-circuits at Step 3).

**Skip this step if `processing_mode: analyze`** — analyze mode produces one analysis note, not numbered claims.

Find the highest existing claim number across the queue and archive to ensure globally unique claim IDs.

```bash
# Check queue for highest claim number in file references
QUEUE_MAX=$(grep -oE '[0-9]{3}\.md' arscontexta/ops/queue*.yaml arscontexta/ops/queue/*.yaml 2>/dev/null | \
  grep -oE '[0-9]{3}' | sort -n | tail -1)
QUEUE_MAX=${QUEUE_MAX:-0}

# Check archive for highest claim number
ARCHIVE_MAX=$(find arscontexta/ops/queue/archive -name "*-[0-9][0-9][0-9].md" 2>/dev/null | \
  grep -v summary | sed 's/.*-\([0-9][0-9][0-9]\)\.md/\1/' | sort -n | tail -1)
ARCHIVE_MAX=${ARCHIVE_MAX:-0}

# Next claim starts after the highest
NEXT_CLAIM_START=$((QUEUE_MAX > ARCHIVE_MAX ? QUEUE_MAX + 1 : ARCHIVE_MAX + 1))
```

Claim numbers are globally unique and never reused across batches. This ensures every claim file name (`{source}-{NNN}.md`) is unique vault-wide.

## Step 7: Create Task File

Write the task file to `arscontexta/ops/queue/${SOURCE_BASENAME}.md`. The template varies by `processing_mode` (determined in Step 3).

### Task file for `extract` mode (default)

```markdown
---
id: {SOURCE_BASENAME}
type: extract
processing_mode: extract
source: {FINAL_SOURCE}
original_path: {original file path before move}
archive_folder: {ARCHIVE_DIR}
created: {UTC timestamp}
next_claim_start: {NEXT_CLAIM_START}
---

# Extract notes from {source filename}

## Source
Original: {original file path}
Archived: {FINAL_SOURCE}
Size: {line count} lines
Content type: {detected type}

## Scope
{scope guidance if provided via --scope, otherwise: "Full document"}

## Acceptance Criteria
- Extract claims, implementation ideas, tensions, and testable hypotheses
- Duplicate check against docs/notes/ during extraction
- Near-duplicates create enrichment tasks (do not skip)
- Each output type gets appropriate handling

## Execution Notes
(filled by /extract)

## Outputs
(filled by /extract)
```

### Task file for `analyze` mode

```markdown
---
id: {SOURCE_BASENAME}
type: extract
processing_mode: analyze
source: {FINAL_SOURCE}
original_path: {original file path before move}
archive_folder: {ARCHIVE_DIR}
created: {UTC timestamp}
---

# Analyze impact of {source filename}

## Source
Original: {original file path}
Archived: {FINAL_SOURCE}
Size: {line count} lines
Content type: {detected type} (design proposal)

## Summary
{Brief summary of what the document proposes — 2-3 sentences from Step 1 reading}

## Guiding Questions
- What does this change for our project?
- Which existing design decisions does it affect?
- Do any existing notes need updating in light of this?
- What should we be watching for as this proposal evolves?

## Related Existing Notes
{List of existing notes found by keyword search in Step 2b — these are the notes most likely to be affected by this proposal}

## Acceptance Criteria
- One analysis note capturing what this means for our project
- Updates or connections to existing notes where affected
- NOT atomic claim decomposition — understand the whole, surface what matters

## Execution Notes
(filled by /extract)

## Outputs
(filled by /extract)
```

## Step 8: Update Queue

Add the extract task entry to the queue file.

**For YAML queues (arscontexta/ops/queue.yaml):**
```yaml
- id: {SOURCE_BASENAME}
  type: extract
  processing_mode: {extract|analyze}
  status: pending
  source: "{FINAL_SOURCE}"
  file: "{SOURCE_BASENAME}.md"
  created: "{UTC timestamp}"
  next_claim_start: {NEXT_CLAIM_START}  # omit for analyze mode
```

**For JSON queues (arscontexta/ops/queue/queue.json):**
```json
{
  "id": "{SOURCE_BASENAME}",
  "type": "extract",
  "processing_mode": "{extract|analyze}",
  "status": "pending",
  "source": "{FINAL_SOURCE}",
  "file": "{SOURCE_BASENAME}.md",
  "created": "{UTC timestamp}",
  "next_claim_start": {NEXT_CLAIM_START}
}
```

For `analyze` mode, omit `next_claim_start` (no numbered claims will be produced).

For `reference` mode, the queue entry is created with `status: done` (no further processing).

**If no queue file exists:** Create one with the appropriate schema header (phase_order definitions) and this first task entry.

## Step 9: Report

### Report for `extract` mode

```
--=={ seed }==--

Seeded: {SOURCE_BASENAME}
Source: {original path} -> {FINAL_SOURCE}
Archive folder: {ARCHIVE_DIR}
Size: {line count} lines
Content type: {detected type}
Processing mode: extract

Task file: arscontexta/ops/queue/{SOURCE_BASENAME}.md
Claims will start at: {NEXT_CLAIM_START}
Claim files will be: {SOURCE_BASENAME}-{NNN}.md (unique across vault)
Queue: updated with extract task

Next steps:
  /ralph 1 --batch {SOURCE_BASENAME}     (extract claims)
  /pipeline will handle this automatically
```

### Report for `analyze` mode

```
--=={ seed }==--

Seeded: {SOURCE_BASENAME}
Source: {original path} -> {FINAL_SOURCE}
Archive folder: {ARCHIVE_DIR}
Size: {line count} lines
Content type: {detected type}
Processing mode: analyze (design proposal — one analysis note, not atomic claims)

Task file: arscontexta/ops/queue/{SOURCE_BASENAME}.md
Queue: updated with analyze task

Next steps:
  /extract {SOURCE_BASENAME}     (analyze impact to our project)
```

### Report for `reference` mode

```
--=={ seed }==--

Archived: {SOURCE_BASENAME}
Source: {original path} -> {FINAL_SOURCE}
Archive folder: {ARCHIVE_DIR}
Size: {line count} lines
Content type: {detected type}
Processing mode: reference (archived, minimal extraction)

Reference note: docs/notes/{reference note title}.md
Queue: reference entry added (status: done)

No further processing needed.
```

---

## Why This Skill Exists

Manual queue management is error-prone. This skill:
- Ensures consistent task file format across batches
- Handles claim numbering automatically (globally unique)
- Checks for duplicates before creating unnecessary work
- Moves sources to their permanent archive location immediately
- Provides clear next steps for the user

## Naming Convention

Task files use the source basename for human readability:
- Task file: `{source-basename}.md`
- Claim files: `{source-basename}-{NNN}.md`
- Summary: `{source-basename}-summary.md`
- Archive folder: `{date}-{source-basename}/`

Claim numbers (NNN) are globally unique across all batches, ensuring every filename is unique vault-wide. This is required because wiki links resolve by filename, not path.

## Source Handling Patterns

**inbox source (most common):**
```
arscontexta/inbox/research/article.md
    | /seed
    v
arscontexta/ops/queue/archive/2026-01-30-article/article.md  <- source moved here
arscontexta/ops/queue/article.md                               <- task file created
```

**Living doc (outside inbox):**
```
CLAUDE.md -> stays as CLAUDE.md (no move)
arscontexta/ops/queue/archive/2026-01-30-claude-md/           <- folder still created
arscontexta/ops/queue/claude-md.md                             <- task file created
```

When /archive-batch runs later, it moves task files into the existing archive folder and generates a summary.

---

## Edge Cases

**Source outside inbox:** Works — source stays in place, archive folder is created for task files only.

**No queue file:** Create `arscontexta/ops/queue/queue.yaml` (or `.json`) with schema header and this first entry.

**Large source (2500+ lines):** Note in output: "Large source ({N} lines) -- /extract will chunk automatically."

**Source is a URL or non-file:** Report error: "/seed requires a file path."

**No arscontexta/ops/derivation-manifest.md:** Use universal vocabulary for all output.

---

## Critical Constraints

**never:**
- Skip duplicate detection (prevents wasted processing)
- Move a source that is not in inbox (living docs stay in place)
- Reuse claim numbers from previous batches (globally unique is required)
- Create a task file without updating the queue (both must happen together)

**always:**
- Ask before proceeding when duplicates are detected
- Create the archive folder even for living docs (task files need it)
- Use the archived path (not original) in the task file for inbox sources
- Report next steps clearly so the user knows what to do next
- Compute next_claim_start from both queue AND archive (not just one)
