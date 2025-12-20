# llm-do

Skills with their own runtime. Like [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills), but each worker runs as a separate agent that can delegate to other workers.

## Why llm-do?

**Delegation.** Workers call other workers like function calls. A summarizer delegates to an analyzer; an orchestrator coordinates specialists. Each runs with its own tools and model.

**Tight context.** Each worker does one thing well. No bloated multi-purpose prompts that try to handle everything.

**Guardrails by construction.** Attachment policies cap resources, tool approvals gate dangerous operations. Guards enforced in code, not prompt instructions. Run in a container for isolation.

**Progressive hardening.** Start with prompts for flexibility. As patterns stabilize, extract deterministic logic to tested Python code. Or go the other direction—soften rigid code into prompts when edge cases multiply. Mix freely: Python calls workers, workers call Python tools, up to 5 levels deep.

## The Model

Workers are focused prompt units that compose like functions:

| Programming | llm-do |
|-------------|--------|
| Function | `.worker` file |
| Function call | Worker tool (same name as worker) |
| Arguments | Input payload |
| Return value | Structured output |

**Why "workers" not "agents"?** llm-do is built on [PydanticAI](https://ai.pydantic.dev/), which uses "agent" for its LLM orchestration primitive. We use "worker" to distinguish our composable, constrained prompt units from the underlying PydanticAI agents that execute them. A worker *defines* what to do; the PydanticAI agent *executes* it.

## Quick Start

```bash
# Install
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."  # or OPENAI_API_KEY

# Run a worker
cd examples/greeter
llm-do "Tell me a joke" --model anthropic:claude-haiku-4-5
```

That's it. The CLI runs `main.worker` in the current directory. Use `--worker` to run a specific worker.

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/) (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o-mini`).

## Project Structure

Projects grow organically from simple to complex:

**Minimal** — just a worker:
```
my-project/
└── orchestrator.worker
```

**With helpers** — orchestrator delegates to focused workers:
```
my-project/
├── orchestrator.worker   # Entry point
├── analyzer.worker       # Focused worker
└── formatter.worker      # Another focused worker
```

**With hardened operations** — extract reliable logic to Python:
```
my-project/
├── orchestrator.worker
├── analyzer.worker
├── tools.py              # Shared Python tools
├── templates/            # Shared Jinja templates
├── input/
└── output/
```

This progression reflects **progressive hardening**: initially you might prompt the LLM to "rename the file to remove special characters". Once you see it works, extract that to a Python function—deterministic, testable, no LLM variability.

## Running Workers

```bash
# Run main.worker in current directory
cd my-project
llm-do "input message" --model anthropic:claude-haiku-4-5

# Run specific worker
llm-do --worker orchestrator "input" --model anthropic:claude-haiku-4-5

# Run from a different directory
llm-do --dir /path/to/project "input" --model anthropic:claude-haiku-4-5

# Override config at runtime
llm-do "input" --model anthropic:claude-sonnet-4 --set locked=true
```

Create a new project:
```bash
llm-do init my-project
```

## Workers

Workers are `.worker` files: YAML front matter (config) + body (instructions). Each worker is exposed as a tool that other workers can call—like function calls.

Add custom tools by creating `tools.py` in your project root:

```python
# tools.py
def sanitize_filename(name: str) -> str:
    """Remove special characters from filename."""
    return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
```

Functions become LLM-callable tools. Reference them in your worker's toolsets config.

## Key Features

- **Worker delegation** — Workers exposed as tools; LLM decides when to call them. Nested calls capped at depth 5
- **Per-worker runtime** — Each worker has its own model, toolset, and attachment policy
- **Custom tools** — Python functions in `tools.py` become LLM-callable tools
- **Tool approvals** — Gate dangerous operations (shell, file writes) for human review
- **Attachment policies** — Control file inputs (size, count, types)
- **Jinja2 templating** — Compose prompts from reusable templates
- **Server-side tools** — Provider-executed capabilities (web search, code execution)

## Examples

See [`examples/`](examples/) for working code:

| Example | Demonstrates |
|---------|--------------|
| [`greeter/`](examples/greeter/) | Minimal project structure |
| [`pitchdeck_eval/`](examples/pitchdeck_eval/) | Multi-worker orchestration, PDF attachments |
| [`calculator/`](examples/calculator/) | Custom Python tools |
| [`approvals_demo/`](examples/approvals_demo/) | Write approval for file operations |
| [`code_analyzer/`](examples/code_analyzer/) | Shell commands with approval rules |
| [`web_searcher/`](examples/web_searcher/) | Server-side tools (web search) |

## Documentation

- **[`docs/concept.md`](docs/concept.md)** — Design philosophy
- **[`docs/cli.md`](docs/cli.md)** — CLI reference
- **[`docs/worker_delegation.md`](docs/worker_delegation.md)** — Worker-to-worker calls
- **[`docs/architecture.md`](docs/architecture.md)** — Internal design
- **[`docs/notes/`](docs/notes/)** — Working design notes and explorations
- **[`docs/notes/archive/`](docs/notes/archive/)** — Historical notes; kept as-is (do not edit)

## Status

**Experimental** — Built on [PydanticAI](https://ai.pydantic.dev/). APIs may change.

**Working:** Worker resolution, worker delegation, approvals, custom tools, templates.

**TUI:** The interactive terminal UI (Textual-based) is experimental. Use `--headless` for non-interactive mode.

**Caveats:** Approvals reduce risk but aren't guarantees. Prompt injection can trick LLMs into misusing granted tools. Treat these as mitigations, not proof of security. Run in a container for real isolation.

## Contributing

PRs welcome! Run `uv run pytest` before committing. See [`AGENTS.md`](AGENTS.md).
