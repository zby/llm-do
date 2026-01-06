# Architecture

Internal architecture of llm-do. For high-level concepts, see [`concept.md`](concept.md).

---

## Workers

A **worker** is an executable prompt artifact: a `.worker` file that defines how to run an LLM-backed task.

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  shell: {}
  filesystem: {}
  analyzer: {}      # another worker
---
Instructions for the worker...
```

Workers can call other workers as tools, forming a call tree. Each worker declares its own toolsets - they're not inherited.

---

## Runtime: Two Scopes

When a worker runs, it operates within two scopes:

**RuntimeConfig** (shared across all workers in a run):
- Approval policy, usage tracking, event callbacks
- Like a web server's global config

**CallFrame** (per-worker):
- Current prompt, message history, nesting depth
- Like a request context - isolated per worker call

This separation means:
- **Shared globally**: Usage tracking, event callbacks, the run-level approval mode (approve-all/reject-all/prompt)
- **Per-worker, no inheritance**: Message history, toolsets, per-tool approval rules

---

## Execution Flow

```
CLI or Python
    │
    ▼
Load .worker file → resolve toolsets
    │
    ▼
run_entry() creates RuntimeConfig + CallFrame
    │
    ▼
Worker builds PydanticAI Agent → runs
    │
    ├── Tool call to another worker?
    │       → new CallFrame (depth+1), same RuntimeConfig
    │       → child runs, returns result
    │
    └── Final output
```

Key points:
- Child workers get fresh message history (parent only sees tool call/result)
- Run-level settings (approval mode, usage tracking) are shared; toolsets are not
- Max nesting depth prevents infinite recursion (default: 5)

---

## Tool Approval

Tools requiring approval are wrapped by `ApprovalToolset`:
- `--approve-all` bypasses prompts (for automation)
- `--reject-all` denies all approval-required tools
- Interactive mode prompts user, caches session approvals

---

## Built-in Toolsets

- **filesystem**: `read_file`, `write_file`, `list_files`
- **shell**: command execution with whitelist-based approval

Python toolsets are discovered from `.py` files. Toolsets can be referenced by alias or full class path.

---

## Calling Workers from Python Tools

Python tools can access the runtime to call other workers or tools. This enables hybrid patterns where deterministic Python code orchestrates LLM reasoning.

### Accepting the Runtime Context

To access the runtime, accept `RunContext[WorkerRuntime]` as the first parameter:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import WorkerRuntime

tools = FunctionToolset()

@tools.tool
async def my_tool(ctx: RunContext[WorkerRuntime], data: str) -> str:
    """Tool that can call workers."""
    result = await ctx.deps.call("worker_name", {"input": data})
    return result
```

The `ctx` parameter is automatically injected by PydanticAI and excluded from the tool schema the LLM sees.

### Calling Workers and Tools

Use `ctx.deps.call(name, input_data)` to invoke any worker or tool by name:

```python
@tools.tool
async def orchestrate(ctx: RunContext[WorkerRuntime], task: str) -> str:
    # Call an LLM worker
    analysis = await ctx.deps.call("analyzer", {"input": task})

    # Call another Python tool
    formatted = await ctx.deps.call("formatter", {"text": analysis})

    return formatted
```

The `input_data` argument is typically a dict with an `"input"` key, but the exact schema depends on the target worker/tool.

### Alternative: Attribute-Style Calls

For convenience, you can use attribute-style syntax via `ctx.deps.tools`:

```python
# These are equivalent:
result = await ctx.deps.call("analyzer", {"input": data})
result = await ctx.deps.tools.analyzer(input=data)
```

### Available Runtime Properties

Via `ctx.deps`, tools can access:

| Property | Description |
|----------|-------------|
| `call(name, input)` | Invoke a worker or tool by name |
| `tools.<name>(**kwargs)` | Attribute-style tool invocation |
| `depth` | Current nesting depth |
| `max_depth` | Maximum allowed depth (default: 5) |
| `model` | Current model identifier |
| `prompt` | Current prompt text |
| `messages` | Conversation history |

### Example: Code Entry Point

A common pattern is using a Python tool as the entry point for deterministic orchestration:

```python
@tools.tool
async def main(ctx: RunContext[WorkerRuntime], input: str) -> str:
    """Orchestrate evaluation of multiple files."""
    files = list(Path("input").glob("*.pdf"))  # deterministic

    results = []
    for f in files:
        # LLM worker handles reasoning
        report = await ctx.deps.call(
            "evaluator",
            {"input": "Analyze this file.", "attachments": [str(f)]}
        )
        Path(f"output/{f.stem}.md").write_text(report)  # deterministic
        results.append(f.stem)

    return f"Processed {len(results)} files"
```

Run with: `llm-do tools.py evaluator.worker --entry main "start"`

This keeps token-intensive orchestration in Python while delegating reasoning to workers.
