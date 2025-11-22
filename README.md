# llm-do

**Treat prompts as executables.** Package prompts with configuration (model, tools, schemas, security constraints) to create workers that LLMs interpret.

## Status

🚧 **Active development** — Currently porting to PydanticAI. The architecture described here is being implemented. The old `llm` plugin-based design is being replaced.

## Core Concept

Workers are self-contained executable units: **prompt + config + tools**. Just like source code is packaged with build configs and dependencies to become executable programs, prompts need packaging to become executable workers.

```yaml
# workers/evaluator.yaml
name: evaluator
description: Evaluate documents using a predefined rubric
model: gpt-4
output_schema_ref: EvaluationResult
sandboxes:
  input:
    path: ./documents
    mode: ro
  output:
    path: ./evaluations
    mode: rw
```

```
# prompts/evaluator.jinja2
Evaluate the attached document using the provided rubric.
Return structured scores and analysis.

Rubric:
{{ file('config/rubric.md') }}
```

Worker instructions are loaded from `prompts/{worker_name}.{jinja2,j2,txt,md}` by
convention. Jinja2 templates support the `file()` function for embedding configuration
files and standard `{% include %}` directives.

Run from CLI:
```bash
cd /path/to/project  # Registry defaults to current working directory

# Load worker by name (checks root level, then workers/ subdirectory)
llm-do evaluator \
  --input '{"rubric": "PROCEDURE.md"}' \
  --attachments document.pdf

# Or specify full path to worker file:
llm-do workers/evaluator.yaml \
  --input '{"rubric": "PROCEDURE.md"}' \
  --attachments document.pdf

# Or specify registry explicitly:
llm-do evaluator \
  --registry ./workers \
  --input '{"rubric": "PROCEDURE.md"}' \
  --attachments document.pdf
```

**Worker discovery convention**: When you specify a worker by name (e.g., `evaluator`),
the registry checks:
1. `{cwd}/evaluator.yaml` (root level)
2. `{cwd}/workers/evaluator.yaml` (workers/ subdirectory)

Root-level workers take precedence over workers/ subdirectory.

Or call from another worker (recursive delegation):
```python
# Inside a worker's agent runtime
result = call_worker("evaluator", input_data={"rubric": "..."}, attachments=["doc.pdf"])
```

## Why This Matters

### 1. Context Bloat
Large workflows with bloated prompts drift and fail unpredictably. When you batch everything into a single prompt, the LLM loses focus.

**Solution**: Decompose into focused sub-calls. Each worker handles a single unit of work ("evaluate exactly this PDF with this procedure") instead of processing everything at once.

### 2. Recursive Calls Are Hard
Making workers call other workers should feel natural, like function calls. But in most frameworks, templates and tools live in separate worlds.

**Solution**: Workers are first-class executables. Delegation is a core primitive with built-in sandboxing, allowlists, and validation.

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

### Example 1: Greeter (Quick Start)

A simple single-worker example to verify your setup works.

**Worker**: `examples/greeter.yaml`
- No sandboxes or special tools
- Just responds to messages conversationally
- Perfect for testing basic functionality

**Run it:**
```bash
cd examples
llm-do greeter.yaml "Hello, how are you?" --model anthropic:claude-sonnet-4-20250514
```

Expected output: Friendly greeting and response with rich formatted message trace showing the full conversation.

---

### Example 2: Pitch Deck Evaluation (Multi-Worker)

A complete workflow demonstrating worker delegation, PDF attachments, and clean I/O separation.

**Scenario**: Analyze PDF pitch decks using a shared evaluation rubric.

**Structure:**
```
examples/pitchdeck_eval/
  workers/
    pitch_orchestrator.yaml  # Orchestrator (handles I/O)
    pitch_evaluator.yaml     # Evaluator (pure analysis)
  prompts/
    pitch_orchestrator.txt   # I/O logic (list PDFs, write reports)
    pitch_evaluator.jinja2   # Analysis logic (read PDF, output markdown)
    PROCEDURE.md            # Evaluation rubric (loaded by Jinja2)
  input/
    *.pdf                   # Drop PDF pitch decks here
  evaluations/              # Generated markdown reports
```

**How it works:**
1. **Orchestrator** lists `.pdf` files in `input/` sandbox
2. For each PDF, **orchestrator** calls **evaluator** via `worker_call()` with PDF as attachment
3. **Evaluator** reads PDF natively (LLM vision), applies rubric, returns markdown report
4. **Orchestrator** writes markdown directly to `evaluations/{slug}.md`

**Design highlights:**
- PDFs passed as **attachments** (not file paths) for native LLM reading
- Evaluator outputs **markdown** (not JSON) - simpler, cleaner
- Clean separation: orchestrator = I/O, evaluator = analysis

**Run it:**
```bash
cd examples/pitchdeck_eval
llm-do pitch_orchestrator \
  "Evaluate all pitch decks in the pipeline" \
  --model anthropic:claude-sonnet-4-20250514 \
  --approve-all
```

Worker is discovered from `workers/pitch_orchestrator.yaml` by convention.

The output shows rich formatted message traces including all tool calls, file operations,
and worker delegations with color-coded panels. The `--approve-all` flag auto-approves
file writes (omit for interactive approval prompts).

**What you'll see:**
- Orchestrator discovers PDF files in `input/`
- For each PDF:
  - Calls `pitch_evaluator` with PDF as attachment
  - Evaluator reads PDF natively and returns markdown
  - Writes markdown report to `evaluations/`
- Rich formatted message trace showing:
  - Sandbox listing
  - Worker delegation with attachments
  - PDF analysis by LLM
  - File writes (with approval prompts)

**Requirements**: Use a model with PDF/vision support (Claude 3.5 Sonnet, GPT-4 Vision, Gemini 1.5 Pro)

**Try it yourself:**
- Add pitch decks: Drop PDF files into `input/`
- Customize rubric: Edit `prompts/PROCEDURE.md` to change evaluation criteria
- Adjust markdown format: Edit `prompts/pitch_evaluator.jinja2` to change report structure
- Tweak I/O logic: Edit `prompts/pitch_orchestrator.txt` to change file handling

**Key features demonstrated:**
- **PDF attachments**: Files passed to workers via `worker_call(attachments=[...])`
- **Native PDF reading**: LLM reads PDFs directly (vision capabilities)
- **Prompts directory convention**: Instructions from `prompts/{worker_name}.{jinja2,txt,md}`
- **Jinja2 templates**: Evaluator loads rubric via `{{ file('prompts/PROCEDURE.md') }}`
- **Markdown output**: Evaluator returns markdown (no JSON conversion needed)
- **Sandboxed I/O**: Orchestrator handles all file operations
- **Worker delegation**: Clean separation of concerns (I/O vs analysis)
- **Tool approval**: Write operations gated by approval system

Each PDF gets isolated evaluation = reproducible, auditable results.

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
