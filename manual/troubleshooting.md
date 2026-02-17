---
description: Common issues, diagnostic patterns, and recovery procedures for the llm-do knowledge system
type: manual
generated_from: "arscontexta-0.8.0"
---

# Troubleshooting

This page covers common issues encountered when using the llm-do knowledge system, diagnostic patterns for identifying problems, and recovery procedures.

## Diagnostic Commands

Before troubleshooting, gather system state:

```bash
# Note count and locations
ls docs/notes/*.md 2>/dev/null | wc -l

# Orphan detection (notes with no incoming links)
for f in docs/notes/*.md; do
  title=$(basename "$f" .md)
  rg -q "\[\[$title\]\]" docs/notes/ || echo "Orphan: $f"
done

# Dangling link detection (links pointing to non-existent files)
rg -o '\[\[([^\]]+)\]\]' docs/notes/ -r '$1' --no-filename | sort -u | while read title; do
  find . -name "$title.md" -not -path "./.git/*" | grep -q . || echo "Dangling: [[$title]]"
done

# Missing descriptions
rg -L '^description:' docs/notes/*.md

# Queue status
cat ops/queue/queue.json 2>/dev/null | python3 -c "
import json, sys
q = json.load(sys.stdin)
tasks = q.get('tasks', [])
by_status = {}
for t in tasks:
    s = t.get('status', 'unknown')
    by_status[s] = by_status.get(s, 0) + 1
for s, c in sorted(by_status.items()):
    print(f'{s}: {c}')
"

# Observation and tension counts
ls ops/observations/*.md 2>/dev/null | wc -l
ls ops/tensions/*.md 2>/dev/null | wc -l
```

Or use the built-in diagnostics:
- `/arscontexta-graph health` -- graph-level diagnostics
- `/arscontexta:health --full` -- comprehensive system audit
- `/arscontexta-stats` -- metrics overview

---

## Common Issues

### Extraction produces zero output from a domain-relevant source

**Symptoms:** `/arscontexta-extract` reports "0 notes extracted" or "all candidates skipped" from a source about llm-do's runtime, agent specs, or harness.

**Cause:** The extraction skill is over-filtering. Common reasons:
- Treating implementation ideas as "not claims" and skipping them
- Rejecting near-duplicates without creating enrichment tasks
- Treating validations of existing approaches as "already known"
- Applying the selectivity gate to domain-relevant content

**Fix:**
1. Check the extraction report for skip reasons
2. Any skip reason of "validates existing approach," "already captured in config," "we already do this," or "obvious" is invalid for domain-relevant sources
3. Re-run extraction with explicit instruction to treat these as extractable categories
4. If the issue recurs: `/arscontexta-remember "extraction over-filters domain-relevant sources"`

**Prevention:** The extraction skill's skip rate target for llm-do sources is < 10%. If consistently higher, check `processing.extraction.selectivity` in ops/config.yaml.

---

### Connect finds no connections for a note

**Symptoms:** `/arscontexta-connect` reports "no connections found" for a note that should clearly relate to existing content.

**Cause:** One of several possibilities:
1. **Vocabulary mismatch** -- the note uses different terms than existing notes for the same concepts (e.g., "tool authorization" vs "approval gates")
2. **Semantic search unavailable** -- the skill fell back to grep-only discovery, which misses same-concept-different-words connections
3. **No relevant index exists** -- the note's topic area has no index, so index browsing finds nothing
4. **Genuinely novel** -- the note covers territory not yet represented in the vault

**Diagnosis:**
```bash
# Check if semantic search is configured
grep 'semantic-search' ops/config.yaml

# Check if the note's topic has an index
rg 'Topics:' "docs/notes/[note-name].md"

# Manually search for related content
rg -i "key concept from note" docs/notes/ --include="*.md"
```

**Fix:**
1. If vocabulary mismatch: search using the note's core concepts, not just title words
2. If semantic search unavailable: consider enabling it (see [[configuration]])
3. If no index: create one when 5+ related notes exist
4. If genuinely novel: ensure the note has a Topics footer linking to the most relevant index, even if it is the only note in that area

---

### Review cold-read prediction always scores 5/5

**Symptoms:** Every note passes the recite test with perfect prediction scores, but notes still feel hard to find.

**Cause:** Descriptions are restating the title rather than adding new information. When the description just rephrases the title, predicting content from title + description is trivially easy, but the description provides no retrieval value.

**Diagnosis:** Read the description. Ask: does it add mechanism, scope, or implication that the title alone does not convey?

- Bad: Title "agent-as-tool unifies calling conventions" / Description "calling conventions are unified through the agent-as-tool pattern"
- Good: Title "agent-as-tool unifies calling conventions" / Description "wrapping agents as tools means the calling LLM cannot distinguish neural from symbolic execution, enabling free refactoring between the two"

**Fix:**
1. Run `/arscontexta-validate all` to find descriptions that fail the "adds info beyond title" check
2. Rewrite flagged descriptions to add mechanism or implication
3. If the issue is systemic: `/arscontexta-remember "descriptions restate titles instead of adding information"`

---

### Queue tasks stuck at a phase

**Symptoms:** Queue entries show `current_phase` that does not advance despite running `/arscontexta-ralph`.

**Cause:**
1. **Phase failure** -- the skill for that phase failed (e.g., review found FAIL-level issues)
2. **Handoff parsing error** -- ralph could not parse the subagent's RALPH HANDOFF block
3. **Queue file corruption** -- invalid JSON in ops/queue/queue.json

**Diagnosis:**
```bash
# Check queue file validity
python3 -c "import json; json.load(open('ops/queue/queue.json'))" 2>&1

# Find stuck tasks
python3 -c "
import json
q = json.load(open('ops/queue/queue.json'))
for t in q.get('tasks', []):
    if t.get('status') == 'pending':
        print(f\"{t['id']}: {t['current_phase']} (completed: {t.get('completed_phases', [])})\")
"
```

**Fix:**
1. If phase failure: check the review output for FAIL reasons, fix the note, re-run the phase
2. If handoff parsing: run the phase manually (`/arscontexta-connect [[note]]`) instead of through ralph
3. If JSON corruption: check git history for the last valid version of ops/queue/queue.json

---

### Dangling wiki links accumulate

**Symptoms:** `/arscontexta-graph health` reports dangling links -- `[[note name]]` references pointing to files that do not exist.

**Cause:**
1. A note was renamed without updating references
2. A link was created to a note that was planned but never written
3. A note was deleted or moved without cleaning up references

**Fix:**
```bash
# Find all dangling links
rg -o '\[\[([^\]]+)\]\]' docs/notes/ -r '$1' --no-filename | sort -u | while read title; do
  find . -name "$title.md" -not -path "./.git/*" | grep -q . || echo "Dangling: [[$title]]"
done

# For each dangling link, decide:
# 1. Create the missing note (if the concept should exist)
# 2. Remove the link (if the reference is stale)
# 3. Update the link (if the target was renamed)
```

**Prevention:** Never rename a note manually. Use the safe rename pattern:
```bash
# Find all references first
rg '\[\[old title\]\]' --glob '*.md' -l
# Then rename and update all references
```

---

### Index grows beyond 40 notes

**Symptoms:** `/arscontexta-graph health` or `/arscontexta-next` warns that an index exceeds the recommended size.

**Cause:** The topic area has grown organically without subdivision. Common for broad topics like "architecture" in a rapidly evolving library like llm-do.

**Fix:**
1. Read the index and identify distinct sub-communities (e.g., "architecture-index" might split into "runtime-architecture-index" and "harness-architecture-index")
2. Run `/arscontexta:architect` with a description of the proposed split
3. Create the sub-indexes, redistribute notes, update the parent index to link to children

**When NOT to split:** If the notes are genuinely about one coherent topic and splitting would create indexes with fewer than 10 notes each.

---

### Orientation phase takes too long

**Symptoms:** Reading self/ and running `/arscontexta-next` consumes significant session time.

**Cause:** self/goals.md has accumulated too many threads, or ops/queue/queue.json is very large.

**Fix:**
1. Clean up self/goals.md -- archive completed threads, consolidate related threads
2. Archive completed queue entries (move done tasks out of the active queue file)
3. Keep self/goals.md focused on 3-5 active threads maximum

---

### Skills report "derivation manifest not found"

**Symptoms:** A skill warns about missing ops/derivation-manifest.md and falls back to universal defaults.

**Cause:** The manifest was not generated during setup, or was accidentally deleted.

**Fix:** Run `/arscontexta:reseed` to regenerate the manifest from ops/derivation.md and current configuration.

---

### Notes created outside the pipeline lack connections

**Symptoms:** Notes written directly to docs/notes/ during development work have no wiki links and do not appear in any index.

**Cause:** Direct writes bypass the connect and review phases of the pipeline.

**Fix:** This is expected behavior, not a bug. After writing a note directly:
1. `/arscontexta-connect [[note name]]` -- find connections and update indexes
2. `/arscontexta-review [note name]` -- verify quality

**Prevention:** The CLAUDE.md instructions note that direct writes are acceptable for design explorations during development -- just run /arscontexta-connect afterward.

---

## Recovery Procedures

### Recovering from queue corruption

If ops/queue/queue.json is corrupted (invalid JSON, lost entries):

```bash
# Check git history for last valid version
git log --oneline -10 -- ops/queue/queue.json

# Restore from git
git show HEAD~1:ops/queue/queue.json > ops/queue/queue.json.bak
# Review the backup, then replace if valid
```

### Rebuilding indexes from scratch

If indexes are out of date or missing:

1. `/arscontexta-graph clusters` -- identify natural topic clusters
2. For each cluster with 5+ notes, create an index
3. `/arscontexta-validate all` -- verify all notes have Topics references

### Resetting processing state

If the queue, observations, and operational state need a clean start:

```bash
# Archive current state
mkdir -p ops/archive/$(date +%Y%m%d)
cp ops/queue/queue.json ops/archive/$(date +%Y%m%d)/
cp -r ops/observations/ ops/archive/$(date +%Y%m%d)/

# Reset queue (empty but valid JSON)
echo '{"tasks": []}' > ops/queue/queue.json

# Notes in docs/notes/ are preserved -- only operational state is reset
```

---

## Getting More Help

- `/arscontexta:help` -- list all available commands
- `/arscontexta:tutorial [topic]` -- interactive walkthrough of a specific capability
- `/arscontexta:ask "your question"` -- query methodology knowledge for guidance
- Read the relevant skill's SKILL.md file in `skills/arscontexta-[name]/SKILL.md` for full implementation details

See [[manual]] for the full manual hub. See [[configuration]] for tuning system behavior. See [[meta-skills]] for system evolution capabilities.
