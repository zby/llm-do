# llm-do

Skills with their own runtime. Like [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills), but each worker runs as a separate agent that can delegate to other workers.

## Why llm-do?

> The way to build useful non-deterministic systems more complex than chat is making them deterministic at key spots.

**Delegation.** Workers call other workers like function calls. A summarizer delegates to an analyzer; an orchestrator coordinates specialists. Each runs with its own tools and model.

**Unified function space.** Workers and Python tools are the same abstraction—they call each other freely. LLM reasoning and deterministic code interleave; which is which becomes an implementation detail.

**Tight context.** Each worker does one thing well. No bloated multi-purpose prompts that try to handle everything. Task executors receive only relevant history—no conversation baggage from parent agents.

**Guardrails by construction.** Attachment policies cap resources, tool approvals gate dangerous operations. Guards enforced in code, not prompt instructions.

**Progressive hardening.** Start with prompts for flexibility. As patterns stabilize, extract deterministic logic to tested Python code. Or go the other direction—soften rigid code into prompts when edge cases multiply.

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

The CLI runs `main.worker` in the current directory. Use `--worker` to run a specific worker. See [`examples/`](examples/) for more.

## Core Concepts

Workers are `.worker` files: YAML front matter (config) + body (instructions). Workers and Python tools form a unified function space—each is exposed as a callable tool, taking input and returning results. LLM reasoning and deterministic code call each other freely (nested calls capped at depth 5):

```
Worker ──calls──▶ Tool ──calls──▶ Worker ──calls──▶ Tool ...
        reason          execute          reason
```

This dual recursion lets each component play to its strengths: LLMs handle ambiguity and context; Python handles precision and speed. See [`docs/concept.md`](docs/concept.md) for the full design philosophy.

**Why "workers" not "agents"?** llm-do is built on [PydanticAI](https://ai.pydantic.dev/), which uses "agent" for its LLM orchestration primitive. We use "worker" to distinguish our composable, constrained prompt units from the underlying PydanticAI agents that execute them. A worker *defines* what to do; the PydanticAI agent *executes* it.

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

This progression reflects progressive hardening: initially you might prompt the LLM to "rename the file to remove special characters". Once you see it works, extract that to a Python function—deterministic, testable, no LLM variability. See [`examples/pitchdeck_eval_hardened`](examples/pitchdeck_eval_hardened/) for a concrete before/after comparison.

## Custom Tools

Add custom tools by creating `tools.py` in your project root:

```python
# tools.py
def sanitize_filename(name: str) -> str:
    """Remove special characters from filename."""
    return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
```

Functions become LLM-callable tools. Reference them in your worker's toolsets config.

To opt into tool context (for calling workers), use `@tool_context` and add a `ctx` param:

```python
# tools.py
from llm_do import tool_context

@tool_context
async def analyze_config(raw: str, ctx) -> str:
    """Delegate parsing to a worker."""
    return await ctx.call_worker("config_parser", raw)
```

You can also use:
- **Jinja2 templates** — Compose prompts from reusable templates in `templates/`
- **Server-side tools** — Provider-executed capabilities like web search and code execution

## CLI Reference

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

# Create a new project
llm-do init my-project
```

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/) (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o-mini`).

See [`docs/cli.md`](docs/cli.md) for full reference.

## Examples

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

## Status

**Experimental** — Built on [PydanticAI](https://ai.pydantic.dev/). APIs may change.

**Working:** Worker resolution, worker delegation, approvals, custom tools, templates.

**TUI:** The interactive terminal UI (Textual-based) is experimental. Use `--headless` for non-interactive mode.

## Security

Tool approvals reduce risk but aren't guarantees. Prompt injection can trick LLMs into misusing granted tools. Treat approvals as one layer of defense.

For real isolation, run llm-do in a container or VM.

## Contributing

PRs welcome! Run `uv run pytest` before committing. See [`AGENTS.md`](AGENTS.md).
