# llm-do

Build LLM workflows where **projects are programs** and **workers are functions**.

Just as complex programs compose focused functions, complex LLM workflows compose focused workers. Each worker does one thing well with tight context—no bloated multi-purpose prompts.

## The Model

| Programming | llm-do |
|-------------|--------|
| Program | Project directory |
| `main()` | `main.worker` |
| Function | `.worker` file |
| Function call | `worker_call` tool |
| Arguments | Input payload |
| Return value | Structured output |

## Quick Start

```bash
# Install
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."  # or OPENAI_API_KEY

# Run a project
llm-do ./examples/greeter "Tell me a joke"
```

That's it. The CLI finds `main.worker` in the project directory and runs it.

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/) (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o-mini`).

## Project Structure

Projects grow organically from simple to complex:

**Minimal** — just an entry point:
```
my-project/
└── main.worker
```

**With helpers** — main delegates to focused workers:
```
my-project/
├── main.worker           # Orchestrator
├── project.yaml          # Shared config (model, sandbox)
└── workers/
    ├── analyzer.worker   # Focused worker
    └── formatter.worker  # Another focused worker
```

**Full project** — tools, templates, and structure:
```
my-project/
├── main.worker
├── project.yaml
├── workers/
│   └── specialist/
│       ├── worker.worker
│       └── tools.py      # Worker-specific tools
├── tools.py              # Project-wide tools
├── templates/            # Shared Jinja templates
├── input/                # Input files (convention)
└── output/               # Output files (convention)
```

## Running Projects

```bash
# Run project (finds main.worker)
llm-do ./my-project "input message"

# Run with different entry point
llm-do ./my-project --entry analyzer "input"

# Run single worker file directly
llm-do ./standalone.worker "input"

# Override config at runtime
llm-do ./my-project "input" --set model=anthropic:claude-sonnet-4
```

Create a new project:
```bash
llm-do init my-project
llm-do init my-project --template pipeline
```

## Workers

Workers are `.worker` files with YAML front matter + instructions:

```yaml
# main.worker
---
name: main
description: Orchestrate document analysis
model: anthropic:claude-haiku-4-5
toolsets:
  worker_call: {}
allow_workers:
  - analyzer
  - formatter
---
You orchestrate document analysis.
1. Call "analyzer" to extract key points
2. Call "formatter" to create the final report
```

Workers call other workers via the `worker_call` tool—like function calls.

### Worker Types

| Type | Structure | Use When |
|------|-----------|----------|
| **Single-file** | `name.worker` | Simple, portable workers |
| **Directory** | `name/worker.worker` | Custom tools, local templates |

Directory workers can have their own `tools.py` and templates that override project-level ones.

## Project Configuration

`project.yaml` provides defaults inherited by all workers:

```yaml
# project.yaml
name: my-project
model: anthropic:claude-haiku-4-5

sandbox:
  paths:
    input:  { root: ./input, mode: ro }
    output: { root: ./output, mode: rw }

toolsets:
  filesystem: {}
```

Workers inherit and can override:
- `model` — worker value wins
- `toolsets` — deep merged (worker adds to project)
- `sandbox.paths` — deep merged (worker adds paths)

## Key Features

**Sandboxed file access** — Workers only access declared directories:
```yaml
sandbox:
  paths:
    input:  { root: ./input, mode: ro, suffixes: [.pdf, .txt] }
    output: { root: ./output, mode: rw }
```

**Custom tools** — Add Python functions in `tools.py`:
```python
# tools.py (project-level) or workers/name/tools.py (worker-level)
def calculate(expression: str) -> float:
    """Evaluate a math expression."""
    return eval(expression)
```

**Jinja2 templating** — Compose prompts from templates:
```yaml
---
name: reporter
---
{% include 'report_template.jinja' %}

Additional instructions here.
```

Templates are searched: worker directory → project `templates/` → built-ins.

**Tool approval system** — Gate dangerous operations:
```yaml
tool_rules:
  - pattern: "shell_*"
    approval: always
  - pattern: "file_write"
    approval: once
```

**Attachment handling** — Control file inputs:
```yaml
attachment_policy:
  max_attachments: 1
  max_total_bytes: 10000000
  allowed_suffixes: [.pdf]
```

**Server-side tools** — Provider-executed capabilities:
```yaml
server_side_tools:
  - tool_type: web_search
    max_uses: 5
```

## Example: Multi-Worker Pipeline

```
pitchdeck_eval/
├── main.worker              # Entry: orchestrates evaluation
├── project.yaml             # Shared model and sandbox config
└── workers/
    ├── pitch_evaluator.worker   # Analyzes pitch decks
    └── report_formatter.worker  # Formats results
```

```bash
llm-do ./pitchdeck_eval --attachments deck.pdf "Evaluate this pitch"
```

The main worker delegates to specialized workers, each with focused context.

See [`examples/`](examples/) for more patterns:
- **`greeter/`** — Minimal project
- **`pitchdeck_eval/`** — Multi-worker orchestration
- **`calculator/`** — Custom tools
- **`code_analyzer/`** — Shell with approval rules
- **`web_searcher/`** — Server-side tools

## Why This Model?

**Tight context.** LLMs perform dramatically better with focused, limited context. A worker trying to do everything is like a 500-line function.

**Composability.** Complex tasks decompose into workers that call workers. The orchestrator doesn't need to know implementation details.

**Guardrails by construction.** Sandboxes, attachment policies, and tool approvals are enforced in code—not suggestions the LLM might ignore.

**Progressive hardening.** Start with prompts for flexibility. As patterns stabilize, extract deterministic logic to Python tools.

## Documentation

- **[`docs/cli.md`](docs/cli.md)** — CLI reference
- **[`docs/architecture.md`](docs/architecture.md)** — Internal design
- **[`docs/worker_delegation.md`](docs/worker_delegation.md)** — Worker-to-worker calls
- **[`docs/notes/worker-function-architecture.md`](docs/notes/worker-function-architecture.md)** — Full specification
- **[`AGENTS.md`](AGENTS.md)** — Development guide

## Status

**Experimental** — Built on [PydanticAI](https://ai.pydantic.dev/). APIs may change.

**Working:** Project detection, worker delegation, sandboxes, approvals, custom tools, templates.

**Caveats:** Sandboxes and approvals reduce risk but aren't guarantees. Prompt injection can trick LLMs into misusing granted tools. Treat these as mitigations, not proof of security.

## Contributing

PRs welcome! Run `.venv/bin/pytest` before committing. See [`AGENTS.md`](AGENTS.md).
