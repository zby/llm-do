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

Schemas must subclass `WorkerArgs` and implement `prompt_spec()`. If omitted, workers use the default `WorkerInput` schema:

```python
from pydantic import Field

from llm_do.runtime import PromptSpec, WorkerArgs

class WorkerInput(WorkerArgs):
    input: str
    attachments: list[str] = Field(default_factory=list)

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=self.input, attachments=tuple(self.attachments))
```

This schema shapes tool-call arguments and validates inputs before the worker runs.
Attachments are still a list of file paths; you can express stricter constraints
via a custom schema if needed.

## Calling Workers from Python

Python code can invoke workers in two contexts:
1. **From orchestrator scripts** — using `Runtime.run_entry()` to start a run
2. **From within tools** — using `ctx.deps.call()` during an active run

### From Orchestrator Scripts

Use `Runtime` to create a shared execution environment and run entries:

```python
from llm_do.runtime import (
    Runtime,
    RunApprovalPolicy,
    WorkerInput,
    build_entry_registry,
)

async def main():
    registry = build_entry_registry(["analyzer.worker"], [])
    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))

    result, ctx = await runtime.run_entry(
        registry,
        entry_name="analyzer",
        input_data=WorkerInput(input="Analyze this data"),
    )

    print(result)
```

`Runtime.run_entry()`:
- Creates a fresh `WorkerRuntime` and `CallFrame` per run
- Reuses runtime-scoped state (usage, approval cache, message log)
- Runtime state is process-scoped (in-memory only, not persisted beyond the process)
- Returns both the result and the runtime context

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `registry` | `EntryRegistry` containing all available entries |
| `entry_name` | Entry point name to run |
| `input_data` | Worker input args (WorkerArgs or dict) |
| `model` | Override the worker's default model |
| `message_history` | Pre-seed conversation history |

Use `Runtime.run_invocable()` if you already have an entry object.

### From Within Tools

Tools can access the runtime to call other workers or tools. This enables hybrid patterns where deterministic Python code orchestrates LLM reasoning.

**Accepting the Runtime Context:**

To access the runtime, accept `RunContext[WorkerRuntime]` as the first parameter:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import WorkerInput, WorkerRuntime

tools = FunctionToolset()

@tools.tool
async def my_tool(ctx: RunContext[WorkerRuntime], data: str) -> str:
    """Tool that can call workers."""
    result = await ctx.deps.call("worker_name", WorkerInput(input=data))
    return result
```

The `ctx` parameter is automatically injected by PydanticAI and excluded from the tool schema the LLM sees.

**Calling Workers and Tools:**

Use `ctx.deps.call(name, input_data)` to invoke any worker or tool by name:

```python
@tools.tool
async def orchestrate(ctx: RunContext[WorkerRuntime], task: str) -> str:
    # Call an LLM worker
    analysis = await ctx.deps.call("analyzer", WorkerInput(input=task))

    # Call another Python tool
    formatted = await ctx.deps.call("formatter", {"text": analysis})

    return formatted
```

`RunContext.prompt` is derived from `WorkerArgs.prompt_spec().text` for logging/UI
only; tools should rely on their typed args and use `ctx.deps` only for delegation.

The `input_data` argument is typically a `WorkerArgs` instance (or dict) with an `"input"` key, but the exact schema depends on the target worker/tool.

**Alternative: Attribute-Style Calls:**

For convenience, you can use attribute-style syntax via `ctx.deps.tools`:

```python
# These are equivalent:
result = await ctx.deps.call("analyzer", WorkerInput(input=data))
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
| `prompt` | Current prompt text (logging/UI only) |
| `messages` | Conversation history |

### Example: Code Entry Point

A common pattern is using a Python function as the entry point for deterministic orchestration. There are two approaches:

**Using @entry decorator (recommended):**

```python
from llm_do.runtime import WorkerArgs, WorkerRuntime, WorkerInput, entry

@entry(name="main", toolsets=["filesystem_project", "evaluator"])
async def process_files(args: WorkerArgs, runtime: WorkerRuntime) -> str:
    """Orchestrate evaluation of multiple files."""
    files = list(Path("input").glob("*.pdf"))  # deterministic

    results = []
    for f in files:
        # LLM worker handles reasoning
        report = await runtime.call(
            "evaluator",
            WorkerInput(input="Analyze this file.", attachments=[str(f)])
        )
        Path(f"output/{f.stem}.md").write_text(report)  # deterministic
        results.append(f.stem)

    return f"Processed {len(results)} files"
```

Run with: `llm-do tools.py evaluator.worker --entry main "start"`

The `@entry` decorator:
- Marks a function as an entry point with a name and toolset references
- Toolsets can be names (resolved during registry linking) or instances
- `schema_in` can specify a `WorkerArgs` subclass for input normalization (defaults to `WorkerInput`)
- The function receives `(args, runtime)`:
  - `args`: `WorkerArgs` instance (normalized input with `prompt_spec()`)
  - `runtime`: `WorkerRuntime` for calling tools via `runtime.call()`

Note: `@entry` functions are trusted code. Tool calls from `runtime.call()` run
directly without approval wrappers; approvals only gate LLM-driven tool calls.

Example with custom input schema:

```python
from llm_do.runtime import PromptSpec, WorkerArgs, WorkerRuntime, entry

class TaggedInput(WorkerArgs):
    input: str
    tag: str

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=f"{self.input}:{self.tag}")

@entry(name="main", schema_in=TaggedInput)
async def main(args: TaggedInput, runtime: WorkerRuntime) -> str:
    return args.tag
```

---

## Writing Toolsets

Toolsets provide tools to workers. There are two approaches:

### FunctionToolset (Decorator-Based)

The simplest way to create tools. Define functions with the `@tools.tool` decorator:

```python
from pydantic_ai.toolsets import FunctionToolset

calc_tools = FunctionToolset()

@calc_tools.tool
def calculate(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression)  # simplified example

@calc_tools.tool
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
  - calc_tools
---
You are a helpful calculator...
```

**Accessing the Runtime:**

To call other workers/tools from your tool, accept `RunContext[WorkerRuntime]`:

```python
from pydantic_ai.tools import RunContext
from llm_do.runtime import WorkerRuntime

@calc_tools.tool
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
from pydantic_ai_blocking_approval import ApprovalResult

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

Toolset configuration lives with the toolset instance in Python. Worker YAML
only references toolset names, so you define any config when instantiating
the toolset in a `.py` file:

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.toolsets import FileSystemToolset

calc_tools = FunctionToolset()
filesystem_data = FileSystemToolset(config={"base_path": "./data", "write_approval": True})
```

Then reference the toolset names in your worker:

```yaml
toolsets:
  - calc_tools
  - filesystem_data
```

If you need to pre-approve specific tools, attach an approval config dict:

```python
calc_tools.__llm_do_approval_config__ = {
    "add": {"pre_approved": True},
    "multiply": {"pre_approved": True},
}
```

**Dependencies:**

Toolset instances are created in Python, so pass any dependencies directly when
instantiating them (e.g., base paths, worker metadata, or sandbox handles).

### Built-in Toolsets

| Name | Class | Tools |
|------|-------|-------|
| `filesystem_cwd` | `FileSystemToolset` | `read_file`, `write_file`, `list_files` (base: CWD) |
| `filesystem_cwd_ro` | `ReadOnlyFileSystemToolset` | `read_file`, `list_files` (base: CWD) |
| `filesystem_project` | `FileSystemToolset` | `read_file`, `write_file`, `list_files` (base: worker dir) |
| `filesystem_project_ro` | `ReadOnlyFileSystemToolset` | `read_file`, `list_files` (base: worker dir) |
| `shell_readonly` | `ShellToolset` | Read-only shell commands (whitelist) |
| `shell_file_ops` | `ShellToolset` | `ls` (pre-approved) + `mv` (approval required) |

---

## Worker File Format

Workers are defined in `.worker` files with YAML frontmatter:

```yaml
---
name: my_worker
model: anthropic:claude-haiku-4-5
toolsets:
  - filesystem_project
  - shell_readonly
  - calc_tools
---
System prompt goes here...

You have access to filesystem and shell tools.
```

**Frontmatter Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Worker identifier (used for `ctx.deps.call()`) |
| `description` | No | Tool description when the worker is exposed as a tool (falls back to `instructions`) |
| `model` | No | Model identifier (e.g., `anthropic:claude-haiku-4-5`) |
| `compatible_models` | No | List of acceptable model patterns (mutually exclusive with `model`) |
| `schema_in_ref` | No | Input schema reference (see [Worker Input Schemas](#worker-input-schemas)) |
| `server_side_tools` | No | Server-side tool configs (e.g., web search) |
| `toolsets` | No | List of toolset names |

**Model Format:**

Models use the format `provider:model-name`:
- `anthropic:claude-haiku-4-5`
- `openai:gpt-4o-mini`
- `ollama:llama3`

**Toolset References:**

Toolsets can be specified as:
- Built-in toolset name (e.g., `filesystem_project`, `shell_readonly`)
- Toolset instance name from a Python file passed to the CLI
- Other worker names from `.worker` files (workers act as toolsets)

**Recursive Workers:**

Workers can opt into recursion by listing themselves in `toolsets`:

```yaml
---
name: explainer
model: anthropic:claude-haiku-4-5
toolsets:
  - explainer
---
Explain the topic, and call yourself for missing prerequisites.
```

Recursion is bounded by `max_depth` (default: 5). Use `--max-depth` in the CLI
or `Runtime(max_depth=...)` in Python to adjust it.

**Compatible Models:**

Use `compatible_models` when you want the worker to accept a CLI/env model that
matches a pattern, rather than hardcoding `model`. Patterns use glob matching:

```yaml
compatible_models:
  - "*"                       # allow any model
  - "anthropic:*"             # any Anthropic model
  - "anthropic:claude-haiku-*"  # any Claude Haiku variant
```

Compatibility checks apply to string model IDs and `Model` objects (Python API).

`model` and `compatible_models` are mutually exclusive.

**Server-Side Tools:**

Use `server_side_tools` to enable provider-hosted tools:

```yaml
server_side_tools:
  - tool_type: web_search
    max_uses: 3
    allowed_domains: ["example.com"]
```

Supported tool types:
- `web_search` (options: `max_uses`, `blocked_domains`, `allowed_domains`)
- `web_fetch`
- `code_execution`
- `image_generation`

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

# Limit recursion depth
llm-do worker.worker --max-depth 3 "prompt"

# Override model
llm-do worker.worker --model openai:gpt-4o "prompt"

# Verbose output
llm-do worker.worker -v "prompt"      # basic
llm-do worker.worker -vv "prompt"     # detailed
```

See [cli.md](cli.md) for full CLI documentation.
