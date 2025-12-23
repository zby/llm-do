# Context-Centric Architecture Design

## Context
Revise the context-centric architecture to explicitly integrate the PydanticAI agent flow while keeping tools and workers unified behind a single callable protocol. Tools use standard PydanticAI signatures with `RunContext[Context]` for seamless integration.

## Implementation Summary

The runtime is anchored on `Context`, which dispatches registry entries and enforces approvals, tracing, depth limits, and model resolution. Tools and workers implement the same callable protocol; the only difference is whether `call()` runs deterministic Python or a PydanticAI agent loop.

### Core Components

**Context** (`ctx.py`)
- Holds registry (per-worker scope), default model, approval function, depth tracking, trace list, and usage dict
- `ctx.run(entry, input)` runs an entry directly (no lookup needed)
- `ctx.call(name, input)` dispatches to tools by name (looked up in registry)
- `ctx.tools.<name>(**kwargs)` provides attribute-style access
- Creates `RunContext[Context]` for tool invocations
- Model resolution: entry's model (if set) or context's default
- Workers get a child context with registry restricted to their declared tools

**ToolEntry** (`entries.py`)
- Wraps a PydanticAI `Tool[Context]` directly
- Name derived from `tool.name` (no duplication)
- Tools use standard PydanticAI signature: `async def my_tool(ctx: RunContext[Context], arg1, arg2) -> T`

**WorkerEntry** (`entries.py`)
- LLM-powered worker with optional model override
- Builds PydanticAI Agent with tools from registry
- Extracts tool traces from PydanticAI messages after execution
- Nested workers wrapped as tools that call back through `ctx.call()`

### Key Design Points

- **Standard PydanticAI tool signatures**
  ```python
  async def my_tool(ctx: RunContext[Context], query: str, limit: int = 10) -> list[dict]:
      # Access orchestration via ctx.deps
      result = await ctx.deps.call("other_tool", {"q": query})
      return result
  ```

- **Model resolution with fallback**
  - Context has a default `model` field
  - WorkerEntry can override with its own `model`
  - ToolEntry has no model (tools don't use LLMs)
  - Resolution: `entry.model if entry.model is not None else ctx.model`

- **Usage tracking by model**
  - `ctx.usage: dict[str, Usage]` tracks token usage per model
  - Aggregates across the entire call graph

- **Unified trace across execution layers**
  - `ctx.call()` adds trace entries for direct calls
  - WorkerEntry extracts tool traces from PydanticAI messages
  - Deduplication: tools called via `ctx.call()` (nested workers) not duplicated
  - Each trace entry: `name`, `kind`, `depth`, `input_data`, `output_data`, `error`

- **Nested worker execution**
  - Nested workers registered as wrapper tools on parent agent
  - Wrapper accepts `**kwargs` to match any input schema
  - Wrapper calls `ctx.deps.call(worker_name, kwargs)`
  - Child context created with incremented depth

### Callable Protocol

```python
class CallableEntry(Protocol):
    name: str
    kind: str  # "tool" or "worker"
    requires_approval: bool
    model: ModelType | None

    async def call(self, input_data: Any, ctx: Context, run_ctx: RunContext[Context]) -> Any:
        ...
```

### Execution Flow

1. Caller uses `ctx.run(entry, input)` for entry points or `ctx.call("tool_name", input)` for tools
2. Context checks depth limit, creates trace entry, checks approval
3. Context resolves model and creates `RunContext[Context]`
4. Context creates child context with `depth + 1` and restricted registry (worker's tools only)
5. Entry's `call()` is invoked with `(input_data, child_ctx, run_ctx)`

**For ToolEntry:**
- Calls `tool.run(run_ctx, input_data)` directly
- PydanticAI handles parameter validation

**For WorkerEntry:**
- Builds PydanticAI Agent with collected tools
- Runs agent with `deps=ctx` (child context)
- Extracts tool traces from `result.new_messages()`
- Returns `result.output`

### Example Usage

```python
from pydantic_ai.tools import RunContext, Tool
from ctx import Context
from entries import ToolEntry, WorkerEntry

# Standard PydanticAI tool signature
async def search(ctx: RunContext[Context], query: str) -> list[str]:
    """Search for documents."""
    return ["doc1.pdf", "doc2.pdf"]

# Create entries
search_tool = ToolEntry(tool=Tool(search, name="search"))

researcher = WorkerEntry(
    name="researcher",
    instructions="Research the topic using available tools.",
    model="anthropic:claude-haiku",  # or None to use ctx.model
    tools=[search_tool],
)

# Run
ctx = Context.from_worker(researcher, model="anthropic:claude-sonnet")
result = await ctx.run(researcher, {"topic": "AI safety"})

# Inspect
for t in ctx.trace:
    print(f"{t.name} ({t.kind}) depth={t.depth}")
print(ctx.usage)
```

### Code Entry Point Pattern (Tool Calling Worker)

A powerful pattern is using a Python tool as the entry point that delegates LLM reasoning to workers. This avoids wasting tokens on trivial orchestration. The tool accesses workers via `ctx.deps.call()`.

See `code_entry_demo.py` for a complete example.

### CLI: llm_do.py

The `llm_do.py` CLI provides a simple way to run workers and tools:

```bash
# Run Python file with "main" entry (auto-discovered)
python llm_do.py file_tools.py "List files in current directory"

# Run worker file with explicit entry
python llm_do.py greeter.worker --entry greeter "Hello!"

# Multiple files with --all-tools
python llm_do.py file_tools.py example_tools.py --all-tools "What's the current dir?"

# Interactive mode
python llm_do.py file_tools.py --interactive

# Custom model
python llm_do.py file_tools.py -m anthropic:claude-sonnet-4 "Hello"

# Show execution trace
python llm_do.py file_tools.py "List files" --trace
```

**Entry point resolution:**
1. If `--entry NAME` specified, use that entry
2. Else if "main" entry exists, use it
3. Else error (no entry point found)

**Options:**
- `--entry/-e NAME`: Specify entry point by name
- `--all-tools/-a`: Make all discovered entries available as tools (escape hatch)
- `--model/-m MODEL`: Override model (default: anthropic:claude-haiku-4-5)
- `--interactive/-i`: Interactive REPL mode
- `--trace`: Show execution trace

**Supported file formats:**

1. **Worker files (`.worker`)** - YAML frontmatter + markdown instructions:
   ```yaml
   ---
   name: greeter
   description: A friendly assistant
   model: anthropic:claude-haiku-4-5  # optional
   ---

   You are a friendly assistant. Greet the user warmly.
   ```

2. **Python files (`.py`)** - Auto-discovers `ToolEntry` and `WorkerEntry` instances:
   ```python
   @tool_entry("list_files")
   async def list_files(ctx: RunContext[Context], path: str) -> list[str]:
       """List files in directory."""
       return [str(p) for p in Path(path).glob("*")]

   # Entry workers should define their tools explicitly
   main = WorkerEntry(
       name="main",
       instructions="You are a file assistant...",
       tools=[list_files],  # explicit tool list
   )
   ```

**Discovery:** The CLI scans module globals for `ToolEntry` and `WorkerEntry` instances. Entry workers should define their own tools explicitly; use `--all-tools` to override and make all discovered entries available.

### Resolved Questions

- **Minimal ctx interface**: Context provides `call()`, `registry`, `model`, `trace`, `usage`, depth tracking
- **RunContext integration**: Tools receive `RunContext[Context]` with `ctx.deps` for orchestration access
- **Trace artifacts**: Both PydanticAI message traces (extracted) and direct call traces are captured
- **Model configuration**: Workers can override context's default model; tools don't need models

### Open Questions

- Should `ToolEntry.call()` be used for direct tool invocation outside agents, or always go through Agent?
- How to handle tool output schema validation (`schema_out`) with PydanticAI's validation?
- Provider/builtin tools integration (web search, code execution) - bypass ctx or wrap?

## Conclusion

The architecture successfully integrates PydanticAI's `RunContext` pattern while maintaining a unified dispatch layer through `Context`. Tools use standard PydanticAI signatures for portability, while the Context layer adds orchestration features: approval control, depth limits, cross-model usage tracking, and unified tracing across nested worker/tool calls.
