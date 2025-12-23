# Context-Centric Runtime Experiment

A lightweight runtime for orchestrating LLM workers and tools with unified tracing, depth limits, and approval control. Uses PydanticAI's `RunContext` and `Tool` primitives directly.

## Quick Start

```bash
cd experiments/context_runtime
uv sync

# Run a simple worker
uv run python llm_do.py greeter.worker "Hello, I'm Alice!"

# Run with custom tools
uv run python llm_do.py example_tools.py "List all Python files here"
```

## CLI: llm_do.py

The main entry point for running workers and tools:

```bash
# Worker file (simple LLM with instructions)
uv run python llm_do.py greeter.worker "Your message"

# Python file with tools (auto-discovered)
uv run python llm_do.py example_tools.py "Your prompt"

# Interactive mode
uv run python llm_do.py example_tools.py --interactive

# Different model
uv run python llm_do.py greeter.worker -m anthropic:claude-sonnet-4 "Hello"
```

## File Formats

### Worker Files (.worker)

Simple LLM workers defined in YAML frontmatter + markdown:

```yaml
---
name: greeter
description: A friendly assistant
model: anthropic:claude-haiku-4-5  # optional
---

You are a friendly assistant. Greet the user warmly.
```

### Python Tool Files (.py)

Define tools using standard PydanticAI signatures:

```python
from pydantic_ai.tools import RunContext
from ctx import Context
from entries import tool_entry

@tool_entry("list_files")
async def list_files(ctx: RunContext[Context], path: str = ".") -> list[str]:
    """List files in a directory."""
    return [str(p) for p in Path(path).glob("*")]
```

Tools are auto-discovered from module-level `ToolEntry` and `WorkerEntry` instances.

## Architecture

**Core Components:**
- `ctx.py` (~165 lines) - Context dispatcher with tracing, depth limits, approval, usage tracking
- `entries.py` (~165 lines) - ToolEntry and WorkerEntry wrapping PydanticAI primitives
- `registry.py` (~23 lines) - Simple name→entry registry

**Key Features:**
- Standard PydanticAI tool signatures: `async def tool(ctx: RunContext[Context], arg1, arg2)`
- Unified tracing across workers and tools
- Model resolution with per-worker override
- Nested worker/tool calls with depth tracking
- Usage tracking by model

## Demos

```bash
# Minimal LLM call
uv run python greeter_demo.py

# Worker with tools
uv run python demo.py

# Nested workers with tools
uv run python pitchdeck_demo.py

# Python tool calling LLM workers
uv run python code_entry_demo.py

# Dynamic worker file loading
uv run python worker_file_demo.py
```

## Design

See `context-centric-architecture-design.md` for the full architecture design.
