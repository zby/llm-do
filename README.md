# llm-do

Package prompts with configuration to create executables.

## Why llm-do?

**Tight context.** Each worker does one thing well. No bloated multi-purpose prompts that try to handle everything.

**Composability.** Workers call other workers like functions. Build complex workflows from simple, focused pieces.

**Guardrails by construction.** Sandboxes limit file access, attachment policies cap resources, tool approvals gate dangerous operations. Guards against LLM mistakes, enforced in code rather than prompt instructions.

**Progressive hardening.** Start with prompts for flexibility. As patterns stabilize, extract deterministic logic to tested Python code.

## The Model

A **project** is a directory with a `main.worker` entry point. Workers are focused prompt units that compose like functions:

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
llm-do ./examples/greeter "Tell me a joke" --model anthropic:claude-haiku-4-5
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

**With hardened operations** — extract reliable logic to Python:
```
my-project/
├── main.worker
├── project.yaml
├── tools.py              # Deterministic operations as functions
├── workers/
│   └── specialist/
│       ├── worker.worker
│       └── tools.py      # Worker-specific tools
├── templates/            # Shared Jinja templates
├── input/
└── output/
```

This progression reflects **progressive hardening**: initially you might prompt the LLM to "rename the file to remove special characters". Once you see it works, extract that to a Python function—deterministic, testable, no LLM variability.

## Running Projects

```bash
# Run project (finds main.worker)
llm-do ./my-project "input message" --model anthropic:claude-haiku-4-5

# Run with different entry point
llm-do ./my-project --entry analyzer "input" --model anthropic:claude-haiku-4-5

# Run single worker file directly
llm-do ./standalone.worker "input" --model anthropic:claude-haiku-4-5

# Override other config at runtime
llm-do ./my-project "input" --model anthropic:claude-sonnet-4 --set locked=true
```

Create a new project:
```bash
llm-do init my-project
```

## Workers

Workers are `.worker` files: YAML front matter (config) + body (instructions). They call other workers via the `worker_call` tool—like function calls.

Add custom tools by creating `tools.py` in your project root:

```python
# tools.py
def sanitize_filename(name: str) -> str:
    """Remove special characters from filename."""
    return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
```

Functions become LLM-callable tools. Reference them in your worker's toolsets config.

## Key Features

- **Sandboxed file access** — Workers only access declared directories with permission controls
- **Worker delegation** — Workers call other workers, with allowlists
- **Custom tools** — Python functions in `tools.py` become LLM-callable tools
- **Jinja2 templating** — Compose prompts from reusable templates
- **Tool approvals** — Gate dangerous operations for human review
- **Attachment policies** — Control file inputs (size, count, types)
- **Server-side tools** — Provider-executed capabilities (web search, code execution)
- **Config inheritance** — `project.yaml` provides defaults, workers override

## Examples

See [`examples/`](examples/) for working code:

| Example | Demonstrates |
|---------|--------------|
| [`greeter/`](examples/greeter/) | Minimal project structure |
| [`pitchdeck_eval/`](examples/pitchdeck_eval/) | Multi-worker orchestration, PDF attachments |
| [`calculator/`](examples/calculator/) | Custom Python tools |
| [`approvals_demo/`](examples/approvals_demo/) | Write approval for sandbox files |
| [`code_analyzer/`](examples/code_analyzer/) | Shell commands with approval rules |
| [`web_searcher/`](examples/web_searcher/) | Server-side tools (web search) |

## Documentation

- **[`docs/concept.md`](docs/concept.md)** — Design philosophy
- **[`docs/cli.md`](docs/cli.md)** — CLI reference
- **[`docs/worker_delegation.md`](docs/worker_delegation.md)** — Worker-to-worker calls
- **[`docs/architecture.md`](docs/architecture.md)** — Internal design

## Status

**Experimental** — Built on [PydanticAI](https://ai.pydantic.dev/). APIs may change.

**Working:** Project detection, worker delegation, sandboxes, approvals, custom tools, templates.

**Caveats:** Sandboxes and approvals reduce risk but aren't guarantees. Prompt injection can trick LLMs into misusing granted tools. Treat these as mitigations, not proof of security.

## Contributing

PRs welcome! Run `.venv/bin/pytest` before committing. See [`AGENTS.md`](AGENTS.md).
