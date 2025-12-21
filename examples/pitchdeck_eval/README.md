# Pitch deck evaluation (PydanticAI workers)

This example demonstrates a clean multi-worker workflow for analyzing pitch deck PDFs:

**Architecture:**
- **Orchestrator** handles all I/O (listing PDFs, saving reports)
- **Evaluator** focuses purely on analysis (receives PDF, returns markdown)

**Files:**
- `workers/pitch_orchestrator.worker` — Orchestrator worker (config + instructions)
- `workers/pitch_evaluator.worker` — Evaluator worker (config + instructions with Jinja2 template)
- `workers/PROCEDURE.md` — Evaluation rubric (loaded by Jinja2 `{{ file() }}`)
- `input/` — Drop PDF pitch decks here for evaluation
- `evaluations/` — Generated markdown reports written here

**Key design:**
- PDFs are passed as **attachments** to the evaluator (LLM reads them natively)
- Evaluator outputs **markdown directly** (no JSON conversion needed)
- Orchestrator writes markdown reports to `evaluations/` directory

## Prerequisites

```bash
pip install -e .            # from the repo root
export ANTHROPIC_API_KEY=...  # or another model provider supported by PydanticAI
```

Both workers leave the `model` field unset so you can choose one at runtime.

**Important:** This example requires a model with native PDF reading capabilities (e.g., Anthropic Claude models). Not all models support PDF attachments—check your model provider's documentation.

## Run the workflow

From the example directory:

```bash
cd examples/pitchdeck_eval
llm-do --model anthropic:claude-haiku-4-5 --approve-all
```

The CLI runs the `main` tool by default (`main.worker` in this example), which orchestrates the evaluation workflow.

Output will show rich formatted message traces including tool calls, file reads, and
worker delegations.

**Flags:**
- `--approve-all`: Auto-approve file writes (recommended for this example)
- `--json`: Output machine-readable JSON instead of rich formatted display
- `--strict`: Reject all non-pre-approved tools (deny-by-default mode)

**What happens:**

1. Orchestrator lists `*.pdf` files in the `input` directory
2. For each PDF:
   - Orchestrator generates a slug from the filename
   - Calls `pitch_evaluator(input="Evaluate this pitch deck.", attachments=["input/deck.pdf"])`
   - Evaluator receives PDF as attachment and reads it natively (vision capabilities)
   - Evaluator returns a complete markdown report
3. Orchestrator writes each report to `evaluations/{slug}.md`
4. CLI shows rich formatted message trace of the entire workflow

**Why this design:**
- **Native PDF reading**: LLM processes PDFs directly (no text extraction needed)
- **Clean separation**: Orchestrator = I/O, Evaluator = analysis
- **Simple output**: Markdown output (no JSON schema, no conversion logic)
- **Attachments**: PDFs flow through the worker delegation system

Open `evaluations/` afterwards to inspect the generated reports.

## Customizing

- **Add pitch decks**: Drop PDF files into `input/`. The LLM reads PDFs natively—
  no conversion needed.
- **Change rubric**: Edit `workers/PROCEDURE.md` to change evaluation criteria.
  The rubric is loaded into the evaluator's instructions via Jinja2.
- **Adjust output format**: Edit the body of `workers/pitch_evaluator.worker` to change the
  markdown structure.
- **Tweak orchestrator logic**: Edit the body of `workers/pitch_orchestrator.worker` to change
  file handling, naming, or processing order.
- **Model selection**: Both workers inherit the model from CLI (`--model` flag).

## Anatomy of the workers

**`pitch_orchestrator`** demonstrates:
- Multiple directories (`input` for input, `evaluations` for output)
- `pitch_evaluator` with **attachments** parameter (passes PDF files)
- `write_file` for saving reports
- Delegation config exposes only the `pitch_evaluator` tool
- File slug generation for consistent naming

**`pitch_evaluator`** demonstrates:
- **Attachment policy** (accepts 1 PDF, max 10MB)
- **No filesystem access** (receives data via attachments, not file system)
- Jinja2 template with `{{ file('PROCEDURE.md') }}` to load rubric
- **Markdown output** (not JSON - simpler, more readable)
- Native PDF reading via LLM vision capabilities

Because both workers inherit `--model` from the CLI, the evaluator automatically
uses a model with PDF/vision support when called by the orchestrator.

## Resetting the example

```bash
rm -f evaluations/*.md
```

Add your own PDF pitch decks to `input/` and rerun the orchestrator to generate
fresh evaluations.

**Note**: You'll need a model with PDF/vision support (e.g., Claude 3.5 Sonnet,
GPT-4 Turbo with Vision, Gemini 1.5 Pro) to process the PDFs natively.
