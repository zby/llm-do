# Pitch deck evaluation demo

This directory shows how to build a workflow entirely out of templates and the
`llm-do` toolboxes.

* `PROCEDURE.md` – canonical rubric shared with every sub-call (a copy also
  lives at `pipeline/PROCEDURE.md` so the sandboxed tools can read it).
* `pipeline/` – drop PDF pitch decks here (empty by default apart from the
  procedure copy).
* `evaluations/` – Markdown reports written here.
* `templates/pitchdeck-single.yaml` – single-deck evaluator (JSON output).
* `templates/pitchdeck-orchestrator.yaml` – orchestrates over every PDF.

Run it with:

```bash
cd examples/pitchdeck_eval
llm -t templates/pitchdeck-orchestrator.yaml \
  "evaluate every pitch deck in pipeline/ using the procedure"
```

You can edit both templates in-place or point the orchestrator at another
sub-template via the `lock_template` parameter. The template prints which files
were processed and where the outputs were written.
