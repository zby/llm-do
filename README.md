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
llm-do evaluator \
  --input '{"rubric": "PROCEDURE.md"}' \
  --attachments document.pdf

# Or specify registry explicitly:
llm-do evaluator \
  --registry ./workers \
  --input '{"rubric": "PROCEDURE.md"}' \
  --attachments document.pdf
```

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

Expected output: Friendly greeting and response in JSON format.

---

### Example 2: Pitch Deck Evaluation (Multi-Worker)

A complete workflow demonstrating worker delegation, sandboxes, and structured outputs.

**Scenario**: Evaluate multiple pitch decks using a shared rubric.

**Structure:**
```
examples/pitchdeck_eval/
  workers/
    pitch_orchestrator.yaml  # Worker definition for orchestration
    pitch_evaluator.yaml     # Worker definition for evaluation
  prompts/
    pitch_orchestrator.txt   # Orchestrator instructions (plain text)
    pitch_evaluator.jinja2   # Evaluator instructions (Jinja2 template)
  config/
    PROCEDURE.md            # Evaluation rubric (configuration)
  input/
    aurora_solar.md         # Sample pitch deck (pure input data)
  evaluations/              # Output directory (reports written here)
```

**How it works:**
1. **Orchestrator** lists `.md` files in `input/` sandbox (read-only)
2. For each deck, **orchestrator** calls **evaluator** worker via `worker_call()`
3. **Evaluator** reads deck file, applies its configured rubric (loaded via `{{file()}}` macro), returns structured JSON
4. **Orchestrator** converts JSON to Markdown report
5. **Orchestrator** writes report to `evaluations/` sandbox (writable)

**Run it:**
```bash
cd examples/pitchdeck_eval
llm-do workers/pitch_orchestrator.yaml \
  "Evaluate all pitch decks in the pipeline" \
  --model anthropic:claude-sonnet-4-20250514

# If you don't want to approve writes interactively:
llm-do workers/pitch_orchestrator.yaml \
  "Evaluate all pitch decks in the pipeline" \
  --model anthropic:claude-sonnet-4-20250514 \
  --approve-all
```

**What you'll see:**
- Orchestrator discovers `aurora_solar.md`
- Delegates evaluation to `pitch_evaluator` worker
- Approval prompt for writing `evaluations/aurora-solar.md` (unless using `--approve-all`)
- Formatted report written to `evaluations/aurora-solar.md`

**Try it yourself:**
- Add more pitch decks: Drop `.md` or `.txt` files into `input/`
- Customize rubric: Edit `config/PROCEDURE.md` to change scoring dimensions
- Adjust worker behavior: Edit `prompts/pitch_evaluator.jinja2` instructions

**Key features demonstrated:**
- **Prompts directory convention**: Instructions loaded from `prompts/{worker_name}.{jinja2,txt,md}` by convention
- **Jinja2 templates**: Evaluator uses `{{ file('config/PROCEDURE.md') }}` to embed rubric (supports full Jinja2 syntax)
- **Sandboxed file access**: Read-only `input/`, writable `evaluations/`
- **Worker delegation**: Orchestrator calls evaluator with `allow_workers` list
- **Model inheritance**: Both workers use CLI-specified model
- **Structured outputs**: Evaluator returns validated JSON
- **Tool approval**: Write operations can be gated (see `tool_rules`)

Each deck gets isolated worker invocation = reproducible results, testable components.

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
