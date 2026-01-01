# llm-do

An imperative orchestration harness for LLM agents. Workers delegate to workers; your code owns control flow.

## Why llm-do?

Most agent frameworks are **graph DSLs**—you define nodes and edges, an engine runs the graph. llm-do is an **imperative orchestration harness**: your code owns control flow, llm-do intercepts at the tool layer. Think syscalls, not state machines.

| Aspect | Graph DSLs | llm-do Harness |
|--------|------------|----------------|
| **Orchestration** | Declarative: define Node A → Node B | Imperative: Worker A calls Worker B as a function |
| **State** | Global context passed through graph | Local scope—each worker receives only its arguments |
| **Approvals** | Checkpoints: serialize graph state, resume after input | Interception: blocking "syscall" at the tool level |
| **Refactoring** | Redraw edges, update graph definitions | Change code—extract functions, inline workers |
| **Control flow** | DSL constructs (branches, loops) | Native Python: `if`, `for`, `try/except` |
| **Durability** | Often built-in checkpointing/replay | None—restart on failure (or integrate external engine) |
| **Visualization** | Graph editors, visual debugging | Code is the source of truth |

> For the full design rationale—including hardening prompts into code (and softening code back to prompts), security posture, and related research—see [`docs/concept.md`](docs/concept.md).

This is the **Unix philosophy for agents**: workers are files, dangerous operations are gated syscalls, composition happens through code—not a DSL.

**Delegation.** Workers call other workers like function calls. A summarizer delegates to an analyzer; an orchestrator coordinates specialists. Each runs with its own tools and model.

**Unified function space.** Workers and Python tools are the same abstraction—they call each other freely. LLM reasoning and deterministic code interleave; which is which becomes an implementation detail.

**Tight context.** Each worker does one thing well. No bloated multi-purpose prompts that try to handle everything. Task executors receive only relevant history—no conversation baggage from parent agents.

**Guardrails by construction.** Tool approvals gate dangerous operations; tool schemas and toolset policies enforce constraints in code, not prompt instructions.

**Progressive hardening.** Start with prompts for flexibility. As patterns stabilize, extract deterministic logic to tested Python code. Or go the other direction—soften rigid code into prompts when edge cases multiply.

## Quick Start

We use [uv](https://docs.astral.sh/uv/) for development. Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh` or see the [installation docs](https://docs.astral.sh/uv/getting-started/installation/).

```bash
# Install
uv pip install -e .  # or: pip install -e .

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."  # or OPENAI_API_KEY

# Optional default model (or use --model per run)
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"

# Run a worker
cd examples/greeter
llm-do main.worker "Tell me a joke"
```

`llm-do` executes the entry point named by `--entry` from the files you pass. If omitted, the entry defaults to `main`, so name your entry worker `main` or pass `--entry` explicitly. See [`examples/`](examples/) for more.

### OAuth Login (Anthropic Pro/Max)

Use the OAuth helper to authenticate with Anthropic subscriptions:

```bash
llm-do-oauth login --provider anthropic
```

Credentials are stored at `~/.llm-do/oauth.json`. Clear them with:

```bash
llm-do-oauth logout --provider anthropic
```

Check login status:

```bash
llm-do-oauth status --provider anthropic
```

## Core Concepts

Workers are `.worker` files: YAML front matter (config) + body (instructions). Workers and Python tools form a unified function space—each is exposed as a callable tool, taking input and returning results. LLM reasoning and deterministic code call each other freely:

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
├── input/
└── output/
```

This progression reflects progressive hardening: initially you might prompt the LLM to "rename the file to remove special characters". Once you see it works, extract that to a Python function—deterministic, testable, no LLM variability. See the pitchdeck examples for a concrete progression: [`pitchdeck_eval`](examples/pitchdeck_eval/) (all LLM) → [`pitchdeck_eval_hardened`](examples/pitchdeck_eval_hardened/) (extracted tools) → [`pitchdeck_eval_code_entry`](examples/pitchdeck_eval_code_entry/) (Python orchestration).

## Custom Tools

Add custom tools by creating `tools.py` in your project root:

```python
# tools.py
from pydantic_ai.toolsets import FunctionToolset

tools = FunctionToolset()

@tools.tool
def sanitize_filename(name: str) -> str:
    """Remove special characters from filename."""
    return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
```

Functions become LLM-callable tools. Reference the toolset name in your worker's `toolsets` config and pass `tools.py` to `llm-do`.

To access runtime context (for calling other tools/workers), accept a `RunContext` and use `ctx.deps`:

```python
# tools.py
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import WorkerRuntime

tools = FunctionToolset()

@tools.tool
async def analyze_config(ctx: RunContext[WorkerRuntime], raw: str) -> str:
    """Delegate parsing to a worker."""
    return await ctx.deps.call("config_parser", {"input": raw})
```

You can also use:
- **Server-side tools** — Provider-executed capabilities like web search and code execution

## CLI Reference

```bash
# Run a worker
llm-do main.worker "input message"

# Run a worker with Python toolsets
llm-do main.worker tools.py "input message"

# Choose a non-default entry
llm-do orchestrator.worker tools.py --entry orchestrator "input"

# Override config at runtime
llm-do main.worker --set model=anthropic:claude-sonnet-4 "input"
```

Common flags: `--headless`, `--tui`, `--chat`, `--json`, `-v/-vv`, `--set`, `--approve-all`, `--model`. See [`docs/cli.md`](docs/cli.md) for details.

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/) (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o-mini`).

See [`docs/cli.md`](docs/cli.md) for full reference.

## Examples

| Example | Demonstrates |
|---------|--------------|
| [`greeter/`](examples/greeter/) | Minimal project structure |
| [`pitchdeck_eval/`](examples/pitchdeck_eval/) | Multi-worker orchestration for pitch decks |
| [`pitchdeck_eval_hardened/`](examples/pitchdeck_eval_hardened/) | Progressive hardening: extracted Python tools |
| [`pitchdeck_eval_code_entry/`](examples/pitchdeck_eval_code_entry/) | Full hardening: Python orchestration, tool entry point |
| [`calculator/`](examples/calculator/) | Custom Python tools |
| [`approvals_demo/`](examples/approvals_demo/) | Write approval for file operations |
| [`file_organizer/`](examples/file_organizer/) | Hardening pattern: LLM semantic decisions + Python cleanup |
| [`code_analyzer/`](examples/code_analyzer/) | Shell commands with approval rules |
| [`web_searcher/`](examples/web_searcher/) | Server-side tools (web search) |

### Running Python Scripts Directly

Some experiments include standalone Python entry points. Run them from the repo root so imports resolve:

```bash
uv run experiments/inv/v2_direct/run.py
uv run -m experiments.inv.v2_direct.run
```

## Documentation

- **[`docs/concept.md`](docs/concept.md)** — Design philosophy
- **[`docs/cli.md`](docs/cli.md)** — CLI reference
- **[`docs/architecture.md`](docs/architecture.md)** — Internal design and worker delegation
- **[`docs/notes/`](docs/notes/)** — Working design notes and explorations

## Status

**Experimental** — Built on [PydanticAI](https://ai.pydantic.dev/). APIs may change.

**Working:** Worker resolution, worker delegation, approvals, custom tools.

**TUI:** The interactive terminal UI (Textual-based) is experimental. Use `--chat` to keep it open for multi-turn input, or `--headless` for non-interactive mode.

## Tradeoffs

llm-do excels at normal-code control flow and progressive hardening. It's not a durable workflow engine—no built-in checkpointing or replay. For that, use llm-do as a component within Temporal, Prefect, or similar.

## Security

Tool approvals reduce risk but aren't guarantees. Prompt injection can trick LLMs into misusing granted tools. Treat approvals as one layer of defense.

For real isolation, run llm-do in a container or VM.

## Contributing

PRs welcome! Run `uv run pytest` before committing. See [`AGENTS.md`](AGENTS.md).
