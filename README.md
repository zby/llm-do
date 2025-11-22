# llm-do

**Treat prompts as executables.** Package prompts with configuration (model, tools, schemas, security constraints) to create workers that LLMs interpret.

## Status

🚧 **Active development** — Currently porting to PydanticAI. The architecture described here is being implemented. The old `llm` plugin-based design is being replaced.

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
- Input data contains `deck_name` for reference

Output format (Markdown):
Return a complete Markdown report with scores and analysis.
```

Worker instructions are loaded from `prompts/{worker_name}.{jinja2,j2,txt,md}` by
convention. Jinja2 templates support the `file()` function for embedding configuration
files (relative to `prompts/` directory) and standard `{% include %}` directives.

Run from CLI:
```bash
cd examples/pitchdeck_eval  # Registry defaults to current working directory

# Load worker by name (discovered from workers/ subdirectory)
llm-do pitch_evaluator \
  --input '{"deck_name": "Aurora Solar"}' \
  --attachments input/aurora-solar.pdf \
  --model anthropic:claude-sonnet-4-20250514

# Or specify full path to worker file:
llm-do workers/pitch_evaluator.yaml \
  --input '{"deck_name": "Aurora Solar"}' \
  --attachments input/aurora-solar.pdf \
  --model anthropic:claude-sonnet-4-20250514
```

**Worker discovery convention**: When you specify a worker by name (e.g., `pitch_evaluator`),
the registry looks for `{cwd}/workers/pitch_evaluator.yaml`.

## Why This Matters

### 1. Context Bloat
Large workflows with bloated prompts drift and fail unpredictably. When you batch everything into a single prompt, the LLM loses focus.

**Solution**: Decompose into focused sub-calls. Each worker handles a single unit of work ("evaluate exactly this PDF with this procedure") instead of processing everything at once.

### 2. Recursive Calls Are Hard
Making workers call other workers should feel natural, like function calls. But in most frameworks, templates and tools live in separate worlds.

**Solution**: Workers are first-class executables. Delegation is a core primitive with built-in sandboxing, allowlists, and validation.

For example, an orchestrator worker can handle I/O while delegating analysis to the evaluator:
```python
# Inside pitch_orchestrator's agent runtime
result = worker_call("pitch_evaluator",
                    input_data={"deck_name": "Aurora Solar"},
                    attachments=["input/aurora-solar.pdf"])
```

The orchestrator lists PDFs, calls the evaluator for each one, and writes the markdown reports—clean separation of concerns with attachment-based file passing.

### 3. Progressive Hardening
Start with flexible prompts that solve problems. Over time, extract deterministic operations (math, formatting, parsing) from prompts into tested Python code. The prompt stays as orchestration; deterministic operations move to functions.

## Key Capabilities

### Sandboxed File Access
Workers read/write files through configured sandboxes:
- Each sandbox has a root directory and access mode (read-only or writable)
- Path escapes blocked by design
- File size limits prevent resource exhaustion

```python
# In a worker's tools
files = sandbox_list("input", "*.pdf")
content = sandbox_read_text("input", files[0])
sandbox_write_text("output", "result.md", report)
```

### Worker-to-Worker Delegation
Workers invoke other workers with controlled inputs:
- Allowlists restrict which workers can be called
- Attachment validation (count, size, extensions) enforced
- Model inheritance: worker definition → caller → CLI → error
- Results can be structured (validated JSON) or freeform text

See [Worker Delegation](docs/worker_delegation.md) for detailed design and examples.

### Tool Approval System
Control which tools execute automatically vs. require human approval:
- Pre-approved tools (read files, call specific workers) execute automatically
- Approval-required tools (write files, create workers) prompt user
- Configurable per-worker and per-tool

### Autonomous Worker Creation
Workers can create specialized sub-workers when they identify the need:
- Subject to approval controls
- User reviews proposed definition before saving
- Created workers start with minimal permissions
- Saved definitions are immediately executable

## Examples

### Example 1: Pitch Deck Evaluation (Multi-Worker)

See `examples/pitchdeck_eval/` for a complete implementation.

This example demonstrates the core design principles of multi-worker systems:

**Clean Separation of Concerns**

The orchestrator handles all I/O (listing files, writing reports), while the evaluator
focuses purely on analysis. This separation makes each worker:
- **Testable**: Pure analysis logic is easy to test with different inputs
- **Reusable**: Evaluator can be called from any workflow needing deck analysis
- **Maintainable**: I/O changes don't affect analysis; rubric changes don't affect I/O

**Attachment-Based File Passing**

Instead of sharing sandboxes or passing file paths, the orchestrator sends PDFs as
attachments via `worker_call(attachments=["input/deck.pdf"])`. The evaluator receives
the PDF directly and uses LLM vision to read it natively—no text extraction, no
preprocessing. This pattern works for any file type the LLM can process.

**Configuration as Code**

The evaluation rubric lives in `prompts/PROCEDURE.md` and gets loaded into the
evaluator's instructions via Jinja2: `{{ file('PROCEDURE.md') }}`. This keeps
configuration close to the prompt logic, version-controlled and auditable. Change
the rubric, get different evaluations—no code changes needed.

**Progressive Refinement**

The evaluator returns simple markdown (not JSON with schemas). This makes iteration
fast: tweak the prompt template, run again, inspect the markdown. Later, if you need
structured output for aggregation, add a schema. Start simple; add structure when
needed.

**Run the example:**
```bash
cd examples/pitchdeck_eval
llm-do pitch_orchestrator \
  "Evaluate all pitch decks" \
  --model anthropic:claude-sonnet-4-20250514 \
  --approve-all
```

The rich formatted output shows every tool call, worker delegation, and approval
decision—full transparency into what the system is doing.

For implementation details, usage patterns, and customization options, see the
[example's README](examples/pitchdeck_eval/README.md).

### Example 2: Greeter (Quick Start)

See `examples/workers/greeter.yaml` for a minimal worker example.

This simple example demonstrates basic worker usage without sandboxes or delegation:

**Minimal Configuration**

The greeter worker is just 12 lines of YAML with inline instructions. No sandboxes, no tools, no schemas—just a friendly conversational agent. This is the fastest way to create an executable worker.

**CLI Model Override**

The worker doesn't specify a model, so you provide one at runtime via `--model`. This lets you experiment with different models (Claude, GPT-4, Gemini) without editing the worker definition.

**Run the example:**
```bash
cd examples
llm-do greeter "Tell me a joke" \
  --model anthropic:claude-sonnet-4-20250514
```

For more details, see the [greeter README](examples/README.md).

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

- **Long-lived references** live under `docs/` (see the files listed above). They describe the intended architecture/spec and should stay current as the code evolves.
- **Short-lived notes** live under `docs/notes/` and are explicitly exploratory. They capture transient investigations that may inform redesigns and can be deleted or promoted later.
- Latest example note: `docs/notes/worker.md` explains the current "what is a worker" story and will be replaced as the redesign lands.
- When a note becomes canonical, move it into the main `docs/` tree and link it here so contributors know which document to trust.

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
- Interactive approval prompts in CLI (callback system works, CLI integration pending)
- Scaffolding builder for project initialization

## Design Principles

1. **Prompts as executables**: Workers are self-contained units you can run from CLI or invoke from other workers
2. **Workers as artifacts**: Definitions saved to disk, version controlled, auditable, refinable
3. **Security by construction**: Sandbox escapes and resource bombs prevented by design, not instructions
4. **Explicit configuration**: Tool access and allowlists declared in definitions, not inherited
5. **Recursive composability**: Worker calls feel like function calls
6. **Sophisticated approval controls**: Balance autonomy with safety

## Contributing

PRs welcome. See `AGENTS.md` for development guidance.

Key points:
- Run `pytest` before committing
- No backwards compatibility constraints (new project)
- Balance simplicity with good design

## Acknowledgements

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.

Inspired by [Simon Willison's llm library](https://llm.datasette.io/) for the concept of templates as executable units.
