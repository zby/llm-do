# Pitch deck evaluation (PydanticAI workers)

This example shows how to build a multi-worker workflow with the new `llm-do`
architecture:

- `workers/pitch_orchestrator.yaml` — worker definition for orchestration.
- `workers/pitch_evaluator.yaml` — worker definition for evaluation.
- `prompts/pitch_orchestrator.txt` — orchestrator instructions (loaded by convention).
- `prompts/pitch_evaluator.jinja2` — evaluator instructions with Jinja2 template
  that loads the rubric via `{{ file('config/PROCEDURE.md') }}`.
- `config/` — configuration files (evaluation rubric `PROCEDURE.md`).
- `input/` — drop Markdown (`.md`/`.txt`) versions of pitch decks here. The
  provided `aurora_solar.md` file acts as a sample input.
- `evaluations/` — destination for generated reports.

## Prerequisites

```bash
pip install -e .            # from the repo root
export ANTHROPIC_API_KEY=...  # or another model provider supported by PydanticAI
```

Both workers leave the `model` field unset so you can choose one at runtime.
Any Claude, OpenAI, or Gemini model exposed through PydanticAI will work.

## Run the workflow

From the example directory:

```bash
cd examples/pitchdeck_eval
llm-do pitch_orchestrator \
  --registry workers \
  --model anthropic:claude-sonnet-4-20250514 \
  --pretty
```

What happens:

1. The orchestrator lists `*.md` and `*.txt` files in the `input` sandbox.
2. For each deck, orchestrator calls `worker_call(worker="pitch_evaluator", input_data={"deck_file": ...})`.
3. The evaluator loads its instructions from `prompts/pitch_evaluator.jinja2`, which
   embeds the rubric via `{{ file('config/PROCEDURE.md') }}`. It reads the deck file
   via `sandbox_read_text`, applies the rubric, produces JSON, and returns it to the orchestrator.
4. The orchestrator converts the JSON to Markdown and saves it with
   `sandbox_write_text("evaluations", "<slug>.md", content)`.
5. CLI output contains a summary plus the path to the generated reports.

Open `evaluations/` afterwards to inspect the Markdown summaries.

## Customizing

- **Add pitch decks**: Drop `.md` or `.txt` files into `input/`. A deck can be
  any Markdown or text file that describes the problem, solution, team,
  traction, and financial model. (Convert PDFs to text before running.)
- **Change rubric**: Edit `config/PROCEDURE.md` to change scoring dimensions.
  The orchestrator sends this to the evaluator, so you can customize evaluation
  criteria without touching code.
- **Adjust workers**: Edit worker YAML definitions to tweak tool policies, change
  sandboxes, or pin specific models.

## Anatomy of the workers

`pitch_orchestrator` demonstrates several primitives from the new runtime:

- Multiple sandboxes (`input` for decks, `evaluations` for output)
- `worker_call` to delegate to a locked evaluator worker
- `sandbox_write_text` for report generation
- Tight `allow_workers` list so only `pitch_evaluator` can run from this worker

`pitch_evaluator` stays focused on evaluation: its instructions are loaded from
`prompts/pitch_evaluator.jinja2`, which uses the `file()` function to embed the
rubric from `config/PROCEDURE.md`. It reads decks from the input sandbox and emits
structured JSON. The rubric is part of the evaluator's configuration (loaded at
worker initialization via Jinja2), not runtime data passed by the orchestrator.
Because both workers inherit whatever `--model` you pass on the CLI, delegation
feels like a normal function call with shared settings.

## Resetting the example

```bash
rm -f evaluations/*.md
```

Leave `aurora_solar.md` (or add your own decks) in `input/` and rerun the
command above to regenerate reports.
