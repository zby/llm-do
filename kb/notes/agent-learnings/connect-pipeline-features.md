# Features to borrow from arscontexta-connect when adding pipeline support

The arscontexta version of /connect (`.claude/skills/arscontexta/arscontexta-connect/SKILL.md`) has pipeline infrastructure that the project_claw version (`project_claw/skills/connect/SKILL.md`) doesn't need yet. When we add pipeline orchestration, revisit these:

## Task file context in Phase 1

When connect runs as part of a pipeline (after an extraction phase), it can read the task file to get upstream context — semantic neighbors, classification, reduce notes. This makes discovery smarter because connect doesn't start cold. Add a conditional step in Phase 1: "If a task file exists (pipeline execution): read it for extraction-phase context."

## File locking on bash qmd fallback

The arscontexta version wraps Tier 2 bash `qmd` calls in a directory-based lock:

```bash
LOCKDIR="project_claw/ops/.locks/qmd.lock"
while ! mkdir "$LOCKDIR" 2>/dev/null; do sleep 2; done
qmd query "..." --collection notes --limit 15
rm -rf "$LOCKDIR"
```

This prevents multiple parallel workers from loading large embedding models simultaneously. Not needed for single-invocation connect, but required if we batch-process multiple notes concurrently (e.g., a ralph-style loop running connect on N notes in parallel).
