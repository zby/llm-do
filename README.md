# llm-do

*A hybrid VM—extend with prompts, stabilize with code.*

LLM reasoning and Python code share a unified execution model. Call a worker (LLM) or a tool (Python) with the same convention. Move computation freely between neural and symbolic—stabilize patterns to code when they emerge, soften rigid code back to LLM when edge cases multiply.

```
[LLM ⟷ Code ⟷ LLM ⟷ Code] → output
```

The boundary is movable. What's neural today can be symbolic tomorrow—and vice versa.

## The Harness Layer

On top of the VM sits a **harness**—an imperative orchestration layer where your code owns control flow. Think syscalls, not state machines.

| Aspect | Graph DSLs | llm-do Harness |
|--------|------------|----------------|
| **Orchestration** | Declarative: define Node A → Node B | Imperative: Worker A calls Worker B as a function |
| **State** | Global context passed through graph | Local scope—each worker receives only its arguments |
| **Approvals** | Checkpoints: serialize graph state, resume after input | Interception: blocking "syscall" at the tool level |
| **Refactoring** | Redraw edges, update graph definitions | Change code—extract functions, inline workers |
| **Control flow** | DSL constructs (branches, loops) | Native Python: `if`, `for`, `try/except` |

> For the theoretical foundation, see [`docs/theory.md`](docs/theory.md). For implementation details, see [`docs/concept.md`](docs/concept.md).

This is the **Unix philosophy for agents**: workers are files, dangerous operations are gated syscalls, composition happens through code—not a DSL.

## Quick Start

We use [uv](https://docs.astral.sh/uv/) for development. Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh` or see the [installation docs](https://docs.astral.sh/uv/getting-started/installation/).

```bash
# Install
uv pip install -e .  # or: pip install -e .

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."  # or OPENAI_API_KEY

# Optional default model (used when a worker omits model)
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"

# Run a project via manifest
llm-do examples/greeter/project.json "Tell me a joke"
```

`llm-do` reads `project.json`, links the listed files, and runs the single entry.
Mark one worker with `entry: true` or define a single `EntrySpec` in Python.
See [`examples/`](examples/) for more.

Example worker file (`main.worker`):

```yaml
---
name: main
entry: true
model: anthropic:claude-haiku-4-5
---
You are a friendly greeter. Respond to the user with a warm, personalized greeting.
Keep your responses brief and cheerful.
```

Example manifest:

```json
{
  "version": 1,
  "runtime": {
    "approval_mode": "prompt",
    "max_depth": 5
  },
  "entry": {
    "input": { "input": "Hello!" }
  },
  "worker_files": ["main.worker"],
  "python_files": ["tools.py"]
}
```

## Core Concepts

**The VM executes two kinds of operations:**

| Operation Type | Implementation | Characteristics |
|----------------|----------------|-----------------|
| **Neural** | Workers (`.worker` files) | Stochastic, flexible, handles ambiguity |
| **Symbolic** | Python tools | Deterministic, fast, cheap, testable |

Orchestration uses `ctx.deps.call_agent(...)` to delegate between agents; entry toolsets are invoked via `call_tool("main", ...)`:

```
Worker ──calls──▶ Tool ──calls──▶ Worker ──calls──▶ Tool ...
 neural          symbolic         neural          symbolic
```

This is **neuro-symbolic computation**: interleaved LLM reasoning and deterministic code, with the boundary between them movable.

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

**With stabilized operations** — extract reliable logic to Python:
```
my-project/
├── orchestrator.worker
├── analyzer.worker
├── tools.py              # Shared Python tools
├── input/
└── output/
```

This progression reflects **moving computation within the VM**: initially you might prompt the LLM to "rename the file to remove special characters". Once you see it works, extract that to a Python function—deterministic, testable, no LLM variability. The operation migrates from neural to symbolic without changing how callers invoke it. See the pitchdeck examples for a concrete progression: [`pitchdeck_eval`](examples/pitchdeck_eval/) (all LLM) → [`pitchdeck_eval_stabilized`](examples/pitchdeck_eval_stabilized/) (extracted tools) → [`pitchdeck_eval_code_entry`](examples/pitchdeck_eval_code_entry/) (Python orchestration).

## Custom Tools

Add custom tools by creating `tools.py` in your project root. Toolsets are
defined as factories via `ToolsetSpec`, so each call gets its own instance:

```python
# tools.py
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def sanitize_filename(name: str) -> str:
        """Remove special characters from filename."""
        return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)

    return tools

tools = ToolsetSpec(factory=build_tools)
```

Functions become LLM-callable tools. Reference the toolset name in your worker's `toolsets` config and list `tools.py` in `project.json` under `python_files`.

To access runtime context (for calling other tools/workers), accept a `RunContext` and use `ctx.deps`:

```python
# tools.py
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec, WorkerRuntime

def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    async def analyze_config(ctx: RunContext[WorkerRuntime], raw: str) -> str:
        """Delegate parsing to another agent."""
        return await ctx.deps.call_agent("config_parser", {"input": raw})

    return tools

tools = ToolsetSpec(factory=build_tools)
```

You can also use:
- **Server-side tools** — Provider-executed capabilities like web search and code execution

## CLI Reference

```bash
# Run a project via manifest
llm-do project.json "input message"

# Use manifest default input (entry.input)
llm-do project.json

# Provide JSON input
llm-do project.json --input-json '{"input":"Hello"}'
```

Common flags: `--headless`, `--tui`, `--chat`, `-v/-vv/-vvv`, `--input-json`, `--debug`. See [`docs/cli.md`](docs/cli.md) for details.

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/) (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o-mini`).

See [`docs/cli.md`](docs/cli.md) for full reference.

## Python Entry Build

If you're orchestrating from Python, link a single entry from files and run it:

```python
import asyncio
from pathlib import Path

from llm_do.runtime import RunApprovalPolicy, Runtime, build_entry

project_root = Path(".").resolve()
entry, registry = build_entry(["main.worker"], ["tools.py"], project_root=project_root)
runtime = Runtime(
    run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    project_root=project_root,
)
runtime.register_agents(registry.agents)

async def main() -> None:
    result, _ctx = await runtime.run_entry(
        entry,
        {"input": "Analyze this data"},
    )
    print(result)


asyncio.run(main())
```

`build_entry()` requires an explicit `project_root`; pass the same root to `Runtime`
to keep filesystem toolsets and attachment resolution aligned.

## Examples

| Example | Demonstrates |
|---------|--------------|
| [`greeter/`](examples/greeter/) | Minimal project structure |
| [`pitchdeck_eval/`](examples/pitchdeck_eval/) | Multi-worker orchestration for pitch decks |
| [`pitchdeck_eval_stabilized/`](examples/pitchdeck_eval_stabilized/) | Progressive stabilizing: extracted Python tools |
| [`pitchdeck_eval_code_entry/`](examples/pitchdeck_eval_code_entry/) | Full stabilizing: Python orchestration, tool entry point |
| [`calculator/`](examples/calculator/) | Custom Python tools |
| [`approvals_demo/`](examples/approvals_demo/) | Write approval for file operations |
| [`file_organizer/`](examples/file_organizer/) | Stabilizing pattern: LLM semantic decisions + Python cleanup |
| [`code_analyzer/`](examples/code_analyzer/) | Shell commands with approval rules |
| [`web_searcher/`](examples/web_searcher/) | Server-side tools (web search) |

### Running Python Scripts Directly

Some experiments include standalone Python entry points. Run them from the repo root so imports resolve:

```bash
uv run experiments/inv/v2_direct/run.py
uv run -m experiments.inv.v2_direct.run
```

## Documentation

- **[`docs/theory.md`](docs/theory.md)** — Theoretical foundation: probabilistic programs, distribution boundaries
- **[`docs/concept.md`](docs/concept.md)** — Design and implementation: how llm-do realizes the theory
- **[`docs/reference.md`](docs/reference.md)** — API reference: calling workers from Python, writing toolsets
- **[`docs/architecture.md`](docs/architecture.md)** — Internal structure: runtime scopes, execution flow
- **[`docs/cli.md`](docs/cli.md)** — CLI reference
- **[`docs/notes/`](docs/notes/)** — Working design notes and explorations

## Status

**Experimental** — Built on [PydanticAI](https://ai.pydantic.dev/). APIs may change.

**Working:** Worker resolution, worker delegation, approvals, custom tools.

**TUI:** The interactive terminal UI (Textual-based) is experimental. Use `--chat` to keep it open for multi-turn input, or `--headless` for non-interactive mode.

## Tradeoffs

llm-do excels at normal-code control flow and progressive stabilizing. It's not a durable workflow engine—no built-in checkpointing or replay. For that, use llm-do as a component within Temporal, Prefect, or similar.

## Security

Tool approvals reduce risk but aren't guarantees. Prompt injection can trick LLMs into misusing granted tools. Treat approvals as one layer of defense.

For real isolation, run llm-do in a container or VM.

## Contributing

PRs welcome! Run `uv run pytest` before committing. See [`AGENTS.md`](AGENTS.md).
