# Context-Centric Runtime Experiment

A lightweight runtime for orchestrating LLM workers and tools with unified tracing, depth limits, and approval control. Uses PydanticAI's `RunContext` and `Tool` primitives directly.

## Quick Start

```bash
cd experiments/context_runtime
uv sync

# Run a worker with tools (file_tools.py has a "main" entry)
uv run python llm_do.py examples/file_tools.py "List all Python files here"

# Run a simple worker file
uv run python llm_do.py examples/greeter.worker --entry greeter "Hello, I'm Alice!"
```

## CLI: llm_do.py

The main entry point for running workers and tools:

```bash
# Python file with main entry (auto-discovered)
uv run python llm_do.py examples/file_tools.py "List files in current directory"

# Worker file with explicit entry
uv run python llm_do.py examples/greeter.worker --entry greeter "Your message"

# Multiple files with --all-tools (makes all entries available)
uv run python llm_do.py examples/file_tools.py examples/example_tools.py --all-tools "What's the current dir?"

# Interactive mode
uv run python llm_do.py examples/file_tools.py --interactive

# Different model
uv run python llm_do.py examples/file_tools.py -m anthropic:claude-sonnet-4 "Hello"

# Show execution trace
uv run python llm_do.py examples/file_tools.py "List files" --trace
```

**Entry point resolution:**
1. If `--entry NAME` specified, use that entry
2. Else if "main" entry exists, use it
3. Else error (no entry point found)

**Options:**
- `--entry/-e NAME`: Specify entry point by name
- `--all-tools/-a`: Make all discovered entries available as tools
- `--model/-m MODEL`: Override model (default: `$LLM_DO_MODEL` env var)
- `--interactive/-i`: Interactive REPL mode
- `--trace`: Show execution trace

**Model Resolution:**
1. Worker's `model` field (if defined)
2. `--model` CLI flag
3. `LLM_DO_MODEL` environment variable
4. Error if none specified

## File Formats

### Worker Files (.worker)

Simple LLM workers defined in YAML frontmatter + markdown:

```yaml
---
name: greeter
description: A friendly assistant
model: anthropic:claude-haiku-4-5  # optional, uses $LLM_DO_MODEL if not set
---

You are a friendly assistant. Greet the user warmly.
```

### Python Tool Files (.py)

Define tools using standard PydanticAI signatures:

```python
from pydantic_ai.tools import RunContext
from src.ctx import Context
from src.entries import tool_entry

@tool_entry("list_files")
async def list_files(ctx: RunContext[Context], path: str = ".") -> list[str]:
    """List files in a directory."""
    return [str(p) for p in Path(path).glob("*")]
```

Tools are auto-discovered from module-level `ToolEntry` and `WorkerEntry` instances.

## Project Structure

```
context_runtime/
├── src/                    # Core runtime
│   ├── ctx.py              # Context dispatcher
│   ├── entries.py          # ToolEntry, WorkerEntry
│   ├── registry.py         # Name→entry registry
│   └── worker_file.py      # .worker file parsing
├── examples/               # Examples and demos
│   ├── file_tools.py       # File tools with main entry
│   ├── example_tools.py    # Standalone tools
│   ├── greeter.worker      # Worker file example
│   ├── demo.py             # Basic demo
│   ├── greeter_demo.py     # Minimal LLM call
│   ├── pitchdeck_demo.py   # Nested workers
│   ├── code_entry_demo.py  # Python entry point
│   └── worker_file_demo.py # Dynamic worker loading
└── llm_do.py               # CLI entry point
```

**Key Features:**
- Standard PydanticAI tool signatures: `async def tool(ctx: RunContext[Context], arg1, arg2)`
- Unified tracing across workers and tools
- Model resolution with per-worker override
- Per-worker registry scope (tools only see declared dependencies)
- Usage tracking by model

## Examples

```bash
# Minimal LLM call
uv run python examples/greeter_demo.py

# Worker with tools
uv run python examples/demo.py

# Nested workers with tools
uv run python examples/pitchdeck_demo.py

# Python tool calling LLM workers
uv run python examples/code_entry_demo.py

# Dynamic worker file loading
uv run python examples/worker_file_demo.py
```

## Design

See `context-centric-architecture-design.md` for the full architecture design.
