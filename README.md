# llm-do

Package prompts with configuration to create executable workers.

A worker is: **prompt + config + tools**. Workers are self-contained units you run from the CLI or call from other workers.

## Why llm-do?

**Tight context.** Each worker does one thing well. No bloated multi-purpose prompts that try to handle everything.

**Composability.** Workers call other workers like functions. Build complex workflows from simple, focused building blocks.

**Guardrails by construction.** Security is enforced in code—sandboxes prevent path traversal, attachment policies prevent resource exhaustion, tool approvals gate dangerous operations. Not suggestions the LLM might ignore.

**Progressive hardening.** Programming with specs (prompts) is powerful for bootstrapping. But as systems grow and compose many parts, stochasticity becomes a liability—especially in key areas. So you progressively harden: replace workers or extract operations to tested Python code.

## Quick Start

```bash
# Install
pip install -e .

# Set your API key (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."

# Set a default model (cheap and fast)
export MODEL=anthropic:claude-3-5-haiku-20241022  # or openai:gpt-4o-mini

# Run a simple worker
cd examples/greeter
llm-do greeter "Tell me a joke" --model $MODEL
```

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/) (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o`).

---

Workers can do much more than simple chat: access files, call other workers, require approvals. Here's a real example that analyzes PDF pitch decks:

```yaml
# workers/pitch_evaluator.yaml
name: pitch_evaluator
description: Analyze a PDF pitch deck and return a markdown evaluation report.
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

...
```

Run it:
```bash
cd examples/pitchdeck_eval

llm-do pitch_evaluator --attachments input/deck.pdf --model $MODEL
```

**Note:** This example requires a model with native PDF reading (e.g., Anthropic Claude models). Not all models support PDF attachments.

## More Examples

Check the `examples/` directory for additional patterns:
- **[`greeter/`](examples/greeter/)** — Minimal conversational worker (shown above)
- **[`pitchdeck_eval/`](examples/pitchdeck_eval/)** — Multi-worker orchestration with PDF analysis (shown above)
- **[`approvals_demo/`](examples/approvals_demo/)** — A demo for tool approval system
- **[`calculator/`](examples/calculator/)** — Custom tools example with mathematical functions
- **`bootstrapping_pitchdeck_eval/`** — Autonomous worker creation workflow

## Key Features

- **Sandboxed file access**: Workers can only read/write within declared directories, with suffix filters and size limits
- **Worker delegation**: Workers call other workers like functions, with built-in allowlists and validation
- **Custom tools**: Add Python functions as tools in `workers/name/tools.py` for domain-specific operations
- **Tool approval system**: Configure which operations run automatically vs. require human review
- **Autonomous worker creation**: Let workers draft new worker definitions (requires approval)
- **Jinja2 templating**: Include files and compose prompts with `{{ file() }}` and `{% include %}`
- **Model flexibility**: Specify models per-worker or override at runtime with `--model`

## How It Works

**Workers** are YAML files that define:
- `name`: Worker identifier
- `description`: What the worker does
- `model`: Which LLM to use (optional, can override with `--model`)
- `instructions`: The prompt (inline or from `prompts/{name}.jinja2`)
- `sandboxes`: Which directories to access (read/write permissions, file filters)
- `tool_rules`: Which tools require approval
- `worker_creation_policy`: Can this worker create new workers?

**Sandboxes** limit file access:
```yaml
sandboxes:
  input:
    root_dir: ./input
    mode: read
    allowed_suffixes: [.pdf, .txt]
  output:
    root_dir: ./output
    mode: write
```

**Worker delegation** lets workers call other workers:
```python
# From within a worker's tools
result = worker_call("pitch_evaluator", attachments=["deck.pdf"])
```

**Custom tools** extend workers with Python code:
```python
# workers/calculator/tools.py
def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
```

Functions in `tools.py` are automatically registered as tools the LLM can call. See [`examples/calculator/`](examples/calculator/) for a complete example.

See [`docs/worker_delegation.md`](docs/worker_delegation.md) for detailed design.

## Documentation

- **[`docs/concept_spec.md`](docs/concept_spec.md)** — Design philosophy and motivation
- **[`docs/worker_delegation.md`](docs/worker_delegation.md)** — Worker-to-worker delegation
- **[`examples/greeter/README.md`](examples/greeter/README.md)** — Simple greeter example
- **[`examples/pitchdeck_eval/README.md`](examples/pitchdeck_eval/README.md)** — Multi-worker example walkthrough
- **[`AGENTS.md`](AGENTS.md)** — Development guide (for AI agents and humans)

## Design Philosophy

1. **Prompts are executables** — Workers are self-contained units you run from CLI or invoke from other workers
2. **Workers are artifacts** — Version controlled, auditable, refinable YAML files on disk
3. **Explicit over implicit** — Tool access and sandboxes declared in worker definitions
4. **Progressive hardening** — Start with flexible prompts, extract deterministic logic to Python tools later
5. **Composability** — Worker delegation feels like function calls

## Current Status

🧪 **Experimental** — Built on PydanticAI. Architecture is functional but APIs may change.

✅ **Working:**
- Worker definitions with YAML persistence
- Sandboxed file access with escape prevention
- Tool approval system
- Worker-to-worker delegation
- CLI with approval modes
- Comprehensive test coverage

🚧 **In Progress:**
- Output schema resolution
- Project scaffolding builder

## Caveats

**Security reality**: Sandboxes, attachment policies, and approval prompts reduce risk but aren't guarantees. Prompt injection and malicious inputs can trick LLMs into misusing granted tools. Treat approvals and sandboxes as mitigations that buy review time, not proof the system is locked down. Assume every worker handles untrusted data.

**Experimental status**: APIs may change. Not production-ready.

## Contributing

PRs welcome! See [`AGENTS.md`](AGENTS.md) for development guidance.

Quick points:
- Run `.venv/bin/pytest` before committing
- Follow `black` formatting, snake_case/PascalCase
- No backwards compatibility promise — breaking changes are fine if they improve design

## Acknowledgements

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.
