# Reference

API and usage reference for llm-do. For concepts, see [concept.md](concept.md). For internals, see [architecture.md](architecture.md).

---

## Worker Input Schemas

Worker files can declare a Pydantic input schema so worker calls (and tool-call
planning) use a structured contract:

```yaml
---
name: evaluator
schema_in_ref: schemas.py:PitchInput
---
```

Supported forms:
- `module.Class`
- `path.py:Class` (relative to the worker file)

If omitted, workers use the default `WorkerInput` schema:

```python
class WorkerInput(BaseModel):
    input: str
    attachments: list[str] = Field(default_factory=list)
```

This schema shapes tool-call arguments and validates inputs before the worker runs.
Attachments are still a list of file paths; you can express stricter constraints
via a custom schema if needed.

## Calling Workers from Python

Python code can invoke workers in two contexts:
1. **From orchestrator scripts** — using `Runtime.run_invocable()` to start a run
2. **From within tools** — using `ctx.deps.call()` during an active run

### From Orchestrator Scripts

Use `Runtime` to create a shared execution environment and run entries:

```python
from llm_do.runtime import (
    Runtime,
    RunApprovalPolicy,
    load_worker_file,
)

async def main():
    worker = load_worker_file("analyzer.worker")
    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))

    result, ctx = await runtime.run_invocable(
        worker,
        prompt="Analyze this data",
    )

    print(result)
```

`Runtime.run_invocable()`:
- Creates a fresh `WorkerRuntime` and `CallFrame` per run
- Reuses runtime-scoped state (usage, approval cache, message log)
- Runtime state is process-scoped (in-memory only, not persisted beyond the process)
- Returns both the result and the runtime context

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `invocable` | Worker or tool to run |
| `prompt` | Input prompt string |
| `model` | Override the worker's default model |
| `message_history` | Pre-seed conversation history |

`run_invocable()` remains as a one-shot convenience wrapper when you don't need a reusable runtime.

### From Within Tools

Tools can access the runtime to call other workers or tools. This enables hybrid patterns where deterministic Python code orchestrates LLM reasoning.

**Accepting the Runtime Context:**

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

**Calling Workers and Tools:**

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

**Alternative: Attribute-Style Calls:**

For convenience, you can use attribute-style syntax via `ctx.deps.tools`:

```python
# These are equivalent:
result = await ctx.deps.call("analyzer", {"input": data})
result = await ctx.deps.tools.analyzer(input=data)
```

**Available Runtime Properties:**

Via `ctx.deps`, tools can access:

| Property | Description |
|----------|-------------|
| `call(name, input_data)` | Invoke a worker or tool by name |
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

---

## Writing Toolsets

Toolsets provide tools to workers. There are two approaches:

### FunctionToolset (Decorator-Based)

The simplest way to create tools. Define functions with the `@tools.tool` decorator:

```python
from pydantic_ai.toolsets import FunctionToolset

tools = FunctionToolset()

@tools.tool
def calculate(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression)  # simplified example

@tools.tool
async def fetch_data(url: str) -> str:
    """Fetch data from a URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text
```

Save as `tools.py` and reference in your worker:

```yaml
---
name: calculator
model: anthropic:claude-haiku-4-5
toolsets:
  tools.py: {}
---
You are a helpful calculator...
```

**Accessing the Runtime:**

To call other workers/tools from your tool, accept `RunContext[WorkerRuntime]`:

```python
from pydantic_ai.tools import RunContext
from llm_do.runtime import WorkerRuntime

@tools.tool
async def analyze(ctx: RunContext[WorkerRuntime], text: str) -> str:
    """Analyze text using another worker."""
    return await ctx.deps.call("sentiment_analyzer", {"input": text})
```

### AbstractToolset (Class-Based)

For more control over tool behavior, approval logic, and configuration, extend `AbstractToolset`:

```python
from typing import Any
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

class MyToolset(AbstractToolset[Any]):
    """Custom toolset with configuration and approval logic."""

    def __init__(self, config: dict):
        self._config = config
        self._require_approval = config.get("require_approval", True)

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        """Define available tools."""
        return {
            "my_tool": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="my_tool",
                    description="Does something useful",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "input": {"type": "string"}
                        },
                        "required": ["input"]
                    },
                ),
            ),
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        """Handle tool calls."""
        if name == "my_tool":
            return f"Processed: {tool_args['input']}"
        raise ValueError(f"Unknown tool: {name}")

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: Any = None,
    ) -> ApprovalResult:
        """Control which calls need approval."""
        if self._require_approval:
            return ApprovalResult.needs_approval()
        return ApprovalResult.pre_approved()

    def get_approval_description(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
    ) -> str:
        """Human-readable description for approval prompts."""
        return f"{name}({tool_args.get('input', '')})"
```

### Toolset Configuration

Toolsets receive configuration from the worker YAML:

```yaml
toolsets:
  filesystem:
    base_path: ./data
    write_approval: true
  my_package.tools.MyToolset:
    custom_setting: value
```

Configuration is passed to the toolset constructor:
- If the constructor accepts `config: dict`, the entire config dict is passed
- Otherwise, config keys are passed as keyword arguments

**Injected Dependencies:**

Toolsets can receive these automatically-injected parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `cwd` | `Path` | Current working directory |
| `worker_name` | `str` | Name of the calling worker |
| `worker_path` | `Path \| None` | Path to the worker file |
| `worker_dir` | `Path \| None` | Directory containing the worker |

### Built-in Toolsets

| Alias | Class | Tools |
|-------|-------|-------|
| `filesystem` | `FileSystemToolset` | `read_file`, `write_file`, `list_files` |
| `shell` | `ShellToolset` | Command execution with approval |

---

## Worker File Format

Workers are defined in `.worker` files with YAML frontmatter:

```yaml
---
name: my_worker
model: anthropic:claude-haiku-4-5
toolsets:
  filesystem: {}
  shell:
    allowed_commands: [ls, cat, grep]
  tools.py: {}
---
System prompt goes here...

You have access to filesystem and shell tools.
```

**Frontmatter Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Worker identifier (used for `ctx.deps.call()`) |
| `model` | No | Model identifier (e.g., `anthropic:claude-haiku-4-5`) |
| `toolsets` | No | Map of toolset references to their configs |

**Model Format:**

Models use the format `provider:model-name`:
- `anthropic:claude-haiku-4-5`
- `openai:gpt-4o-mini`
- `ollama:llama3`

**Toolset References:**

Toolsets can be specified as:
- Built-in alias: `filesystem`, `shell`
- Python file path: `tools.py`, `./lib/helpers.py`
- Fully-qualified class: `my_package.toolsets.CustomToolset`

---

## CLI Quick Reference

```bash
# Run a worker
llm-do worker.worker "prompt"

# Run with tools file
llm-do tools.py worker.worker "prompt"

# Specify entry point
llm-do tools.py worker.worker --entry main "prompt"

# Approval modes
llm-do worker.worker --approve-all "prompt"
llm-do worker.worker --reject-all "prompt"

# Override model
llm-do worker.worker --model openai:gpt-4o "prompt"

# Verbose output
llm-do worker.worker -v "prompt"      # basic
llm-do worker.worker -vv "prompt"     # detailed
```

See [cli.md](cli.md) for full CLI documentation.
