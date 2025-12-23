# Context-Centric Architecture Design

## Context
Revise the context-centric architecture to explicitly integrate the PydanticAI agent flow while keeping tools and workers unified behind a single callable protocol. Tools use standard PydanticAI signatures with `RunContext[Context]` for seamless integration.

## Implementation Summary

The runtime is anchored on `Context`, which dispatches registry entries and enforces approvals, tracing, depth limits, and model resolution. Tools and workers implement the same callable protocol; the only difference is whether `call()` runs deterministic Python or a PydanticAI agent loop.

### Core Components

**Context** (`ctx.py`)
- Holds registry, default model, approval function, depth tracking, trace list, and usage dict
- `ctx.call(name, input)` dispatches to tools/workers with approval checks and tracing
- `ctx.tools.<name>(**kwargs)` provides attribute-style access
- Creates `RunContext[Context]` for tool invocations
- Model resolution: entry's model (if set) or context's default

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

1. Caller uses `ctx.call("analyze", input)` or `await ctx.tools.analyze(**kwargs)`
2. Context checks depth limit, creates trace entry, checks approval
3. Context resolves model and creates `RunContext[Context]`
4. Context creates child context with `depth + 1`
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
result = await ctx.call("researcher", {"topic": "AI safety"})

# Inspect
for t in ctx.trace:
    print(f"{t.name} ({t.kind}) depth={t.depth}")
print(ctx.usage)
```

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
