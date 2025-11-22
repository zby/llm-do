# llm-do

**Treat prompts as executables.** Package prompts with configuration (model, tools, schemas, security constraints) to create workers that LLMs interpret.

## Status

🧪 **Experimental** — Built on PydanticAI for agent runtime and structured outputs. The architecture is functional but APIs may change.

## Security Reality

Sandboxes, attachment policies, and approval prompts reduce the blast radius of mistakes,
but they are not security guarantees. Prompt-injection and malicious inputs can still trick
an LLM into abusing granted tools, so assume every worker is handling untrusted data.
Treat the approval layer and sandbox config as mitigations that buy you review time—not as
proof that the system is locked down.

## Core Concept

Workers are self-contained executable units: **prompt + config + tools**. Just like source code is packaged with build configs and dependencies to become executable programs, prompts need packaging to become executable workers.

```yaml
# workers/pitch_evaluator.yaml
name: pitch_evaluator
description: Analyze a PDF pitch deck and return a markdown evaluation report
attachment_policy:
  max_attachments: 1
  max_total_bytes: 10000000  # 10MB
  allowed_suffixes:
    - .pdf
```

```jinja2
# prompts/pitch_evaluator.jinja2
You are a pitch deck evaluation specialist. You will receive a pitch deck PDF
as an attachment and must analyze it according to the evaluation rubric below.

Evaluation rubric:
{{ file('PROCEDURE.md') }}

Input:
- You will receive the deck as a PDF attachment (the LLM can read PDFs natively)

Output format (Markdown):
Return a complete Markdown report with scores and analysis.
```

Worker instructions can be provided inline (raw text only) or loaded from `prompts/{worker_name}.{jinja2,j2,txt,md}`.
File-based prompts with `.jinja2` or `.j2` extensions support Jinja2 templating, including the `file()` function
and `{% include %}` directives. Inline instructions are **always** treated as raw text and are never rendered.

Run from CLI:
```bash
cd examples/pitchdeck_eval  # Registry defaults to current working directory

# Load worker by name (discovered from workers/ subdirectory)
llm-do pitch_evaluator \
  --attachments input/acma_pitchdeck.pdf \
  --model anthropic:claude-haiku-4-5

# Or specify full path to worker file:
llm-do workers/pitch_evaluator.yaml \
  --attachments input/acma_pitchdeck.pdf \
  --model anthropic:claude-haiku-4-5
```

**Worker discovery convention**: When you specify a worker by name (e.g., `pitch_evaluator`),
the registry looks for `{cwd}/workers/pitch_evaluator.yaml`. The package also ships with
reference workers under `llm_do/workers/` that you can run directly or copy into your own
project to remix.

## Why This Matters

- **Focused context**: Bloated prompts drift. Workers keep each task scoped ("evaluate this deck with this rubric"), so the LLM does not juggle unrelated goals.
- **Delegation feels native**: `worker_call("pitch_evaluator", attachments=["input/acma_pitchdeck.pdf"])` feels like a function call with allowlists and attachment validation built in, keeping orchestrators small.
- **Progressive hardening**: Start with flexible prompts, then move deterministic logic into Python tools once you understand the workflow.

The orchestrator lists PDFs, calls the evaluator for each one, and writes the markdown reports—clean separation of concerns with attachment-based file passing.

### 3. Progressive Hardening
Start with flexible prompts that solve problems. Over time, extract deterministic operations (math, formatting, parsing) from prompts into tested Python code. The prompt stays as orchestration; deterministic operations move to functions.

## Key Capabilities

- **Sandboxed file access** keeps I/O inside declared roots with explicit read/write modes,
  suffix filters, and size caps. Use attachments for binary files so the model reads them directly.

```python
# In a worker tool
files = sandbox_list("input", "*.pdf")
content = sandbox_read_text("input", files[0])
sandbox_write_text("output", "result.md", report)
```

`sandbox_read_text` only opens UTF-8 text. Passing `attachments=["input/deck.pdf"]`
into a downstream worker hands the binary to the LLM without leaking broader access.

- **Worker-to-worker delegation** means `worker_call`/`worker_create` enforce allowlists,
  attachment budgets, and optional schemas. Orchestrators stay small while specialized
  workers focus on analysis.

- **Tool approval system** lets you decide which tools run automatically versus pause for
  review. Treat approvals as a brake pedal—if a prompt is compromised it can still abuse
  whatever tools you allow.

- **Autonomous worker creation** lets a worker draft new definitions under tight sandboxes.
  Proposals require human approval and start with minimal permissions, but once accepted
  they are first-class artifacts on disk.

## Examples

### Example 1: Pitch Deck Evaluation (Multi-Worker)

`examples/pitchdeck_eval/` shows how an orchestrator lists decks, hands each PDF to a
specialized evaluator, and writes markdown reports. Key takeaways:
- Clean separation: orchestrator = I/O, evaluator = analysis, so each worker is testable.
- Attachments move files between workers without exposing extra filesystem access.
- Rubrics live in `prompts/PROCEDURE.md` and are injected via `{{ file('PROCEDURE.md') }}`.
- Start with markdown output; add schemas later if you need structure.

Run it with:
```bash
cd examples/pitchdeck_eval
llm-do pitch_orchestrator \
  "Evaluate all pitch decks" \
  --model anthropic:claude-sonnet-4-5 \
  --approve-all
```

The CLI trace shows every tool call and approval prompt. See
`examples/pitchdeck_eval/README.md` for deep dives.

### Example 2: Greeter (Quick Start)

`examples/workers/greeter.yaml` is a 12-line worker with inline instructions. No sandboxes, no tools, no schemas—just a friendly conversational agent you can tweak instantly.

- Override the model at runtime with `--model` to experiment without editing the file.
- Use it as a template when you want to spin up a conversational helper fast.

Run it with:
```bash
cd examples
llm-do greeter "Tell me a joke" \
  --model anthropic:claude-haiku-4-5
```

See `examples/README.md` for more lightweight workers.

## Progressive Hardening Workflow

1. **Autonomous creation**: Worker creates specialized sub-worker, user approves
2. **Testing**: Run tasks, observe behavior
3. **Iteration**: Edit saved definition—refine prompts, add schemas
4. **Locking**: Pin orchestrators to vetted worker definitions via allowlists
5. **Migration**: Extract deterministic operations to tested Python functions

Workers stay as orchestration layer; Python handles deterministic operations.

## Architecture

```
llm_do/
  pydanticai/
    __init__.py
    base.py              # Core runtime: registry, sandboxes, delegation
    cli.py               # CLI entry point with mock runner support

tests/
  test_pydanticai_base.py
  test_pydanticai_cli.py

docs/
  concept_spec.md           # Detailed design philosophy
  worker_delegation.md      # Worker-to-worker delegation design
  pydanticai_architecture.md
  pydanticai_base_plan.md
```

## Documentation Map

- **Stable references** live under `docs/`:
  - `concept_spec.md` — Design philosophy and motivation
  - `worker_delegation.md` — Worker-to-worker delegation design
  - `message_display.md` — CLI output formatting
- **Exploratory notes** live under `docs/notes/`:
  - `worker.md` — Implementation notes and open questions
- **Example documentation** lives with the examples:
  - `examples/pitchdeck_eval/README.md` — Multi-worker delegation example
  - `examples/README.md` — Quick start examples

## Installation

Not yet published to PyPI. Install in development mode:

```bash
pip install -e .
```

Dependencies:
- `pydantic-ai>=0.0.13`
- `pydantic>=2.7`
- `PyYAML`

## Current Status

✅ **Core functionality complete:**
- Worker artifacts (definition/spec/defaults) with YAML persistence
- WorkerRegistry with file-backed storage and CWD defaults
- Sandboxed file access with escape prevention
- Tool approval system with configurable policies
- Worker-to-worker delegation (`worker_call`, `worker_create` tools)
- Model inheritance chain (definition → caller → CLI)
- CLI with approval modes (`--approve-all`, `--strict`)
- Comprehensive test coverage with mock models

🚧 **In progress:**
- Output schema resolution (pluggable resolver exists, needs production implementation)
- Scaffolding builder for project initialization

## Design Principles

1. **Prompts as executables**: Workers are self-contained units you can run from CLI or invoke from other workers
2. **Workers as artifacts**: Definitions saved to disk, version controlled, auditable, refinable
3. **Security-first defaults**: Sandboxes, allowlists, and approvals lower risk but cannot eliminate prompt-injection or abuse
4. **Explicit configuration**: Tool access and allowlists declared in definitions, not inherited
5. **Recursive composability**: Worker calls feel like function calls
6. **Sophisticated approval controls**: Balance autonomy with safety

## Contributing

PRs welcome. See `AGENTS.md` for development guidance.

Key points:
- Run `pytest` before committing
- Balance simplicity with good design

## Acknowledgements

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.
