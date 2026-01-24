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

Schemas must subclass `WorkerArgs` and implement `prompt_messages()`. Input can be passed in several forms:

```python
# Simple string
await ctx.deps.call_agent("worker", "text")

# With attachments
await ctx.deps.call_agent("worker", {"input": "text", "attachments": ["file.pdf"]})
```

For custom schemas, subclass `WorkerArgs`:

```python
from llm_do.runtime import PromptContent, WorkerArgs

class PitchInput(WorkerArgs):
    input: str
    company_name: str

    def prompt_messages(self) -> list[PromptContent]:
        return [f"Evaluate {self.company_name}: {self.input}"]
```

This schema shapes tool-call arguments and validates inputs before the worker runs.

## Entry Selection

When loading entries from files, there must be exactly one entry candidate:
- **Worker files**: mark the entry worker with `entry: true` in frontmatter
- **Python files**: define a single `EntrySpec` instance

If multiple candidates exist (or none), loading fails with a descriptive error.

## Calling Agents from Python

Python code can invoke agents in two contexts:
1. **From orchestrator scripts** — using `Runtime.run_entry()` to start a run
2. **From within tools** — using `ctx.deps.call_agent()` during an active run

### From Orchestrator Scripts

Use `Runtime` to create a shared execution environment and run entries:

```python
from pathlib import Path

from llm_do.runtime import (
    Runtime,
    RunApprovalPolicy,
    build_entry,
)

async def main():
    project_root = Path(".").resolve()
    entry_spec, registry = build_entry(["analyzer.worker"], [], project_root=project_root)
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        project_root=project_root,
    )
    runtime.register_agents(registry.agents)

    result, ctx = await runtime.run_entry(
        entry_spec,
        input_data="Analyze this data",
    )

    print(result)
```

`Runtime.run_entry()`:
- Creates a fresh entry runtime (NullModel, no toolsets) for the entry function
- Reuses runtime-scoped state (usage, approval cache, message log)
- Runtime state is process-scoped (in-memory only, not persisted beyond the process)
- Returns both the result and the runtime context
 
`build_entry()` returns `(EntrySpec, AgentRegistry)` and requires an explicit `project_root`; pass the same root to `Runtime`
to keep filesystem toolsets and attachment resolution aligned.

Workers resolve their model at construction (`model` in the worker definition or
`LLM_DO_MODEL` as a fallback). Entry functions run under NullModel (no toolsets),
so direct LLM calls from entry code are not allowed.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `entry_spec` | `EntrySpec` to run (plain `main` function) |
| `input_data` | Input payload (str, list of prompt parts, dict, or `WorkerArgs`) |
| `message_history` | Pre-seed conversation history for the top-level call scope |

Use `Runtime.run()` for sync execution when you already have an entry object.

### Multi-Turn Entries (message_history)

For chat-style flows, carry forward `message_history` between turns:

```python
from pathlib import Path

from llm_do.runtime import Runtime, build_entry

async def main():
    project_root = Path(".").resolve()
    entry_spec, registry = build_entry(["assistant.worker"], [], project_root=project_root)
    runtime = Runtime(project_root=project_root)
    runtime.register_agents(registry.agents)

    message_history = None
    result, ctx = await runtime.run_entry(entry_spec, {"input": "turn 1"})
    message_history = list(ctx.frame.messages)

    result, ctx = await runtime.run_entry(
        entry_spec,
        {"input": "turn 2"},
        message_history=message_history,
    )
```

The top-level agent consumes `message_history` on each turn at depth 0.

### From Within Tools

Tools can access the runtime to call other agents. This enables hybrid patterns where deterministic Python code orchestrates LLM reasoning.

**Accepting the Runtime Context:**

To access the runtime, accept `RunContext[WorkerRuntime]` as the first parameter:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec, WorkerRuntime

def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    async def my_tool(ctx: RunContext[WorkerRuntime], data: str) -> str:
        """Tool that can call agents."""
        result = await ctx.deps.call_agent("worker_name", data)
        return result

    return tools

tools = ToolsetSpec(factory=build_tools)
```

The `ctx` parameter is automatically injected by PydanticAI and excluded from the tool schema the LLM sees.

**Calling Agents:**

Use `ctx.deps.call_agent(spec_or_name, input_data)` to invoke an agent by name or `AgentSpec`:

```python
@tools.tool
async def orchestrate(ctx: RunContext[WorkerRuntime], task: str) -> str:
    # Call an LLM agent
    analysis = await ctx.deps.call_agent("analyzer", task)
    return analysis
```

`RunContext.prompt` is derived from `WorkerArgs.prompt_messages()` for logging/UI
only; tools should rely on their typed args and use `ctx.deps` only for delegation.

The `input_data` argument can be a string, list (with `Attachment`s), dict, or `WorkerArgs`.

**Available Runtime State:**

Via `ctx.deps`, tools can access (depth lives at `ctx.deps.frame.depth`, and limits at `ctx.deps.config.max_depth`):

| Property | Description |
|----------|-------------|
| `call_agent(spec_or_name, input_data)` | Invoke an agent by name or `AgentSpec` |
| `frame` | Call state (`depth`, `model`, `prompt`, `messages`, `active_toolsets`) |
| `config` | Runtime config (`max_depth`, approval policy, verbosity, etc.) |

### Example: Code Entry Point

A common pattern is using a Python function as the entry point for deterministic orchestration:

```python
from pathlib import Path

from llm_do.runtime import EntrySpec, WorkerRuntime

async def main(_input_data, runtime: WorkerRuntime) -> str:
    """Orchestrate evaluation of multiple files."""
    files = list(Path("input").glob("*.pdf"))  # deterministic

    results = []
    for f in files:
        # LLM agent handles reasoning
        report = await runtime.call_agent(
            "evaluator",
            {"input": "Analyze this file.", "attachments": [str(f)]},
        )
        Path(f"output/{f.stem}.md").write_text(report)  # deterministic
        results.append(f.stem)

    return f"Processed {len(results)} files"

ENTRY_SPEC = EntrySpec(name="main", main=main)
```

Run with a manifest that includes `tools.py` and `evaluator.worker`, e.g.
`llm-do project.json "start"` (the single `EntrySpec` is selected automatically).

`EntrySpec` fields:
- `name`: Entry name for logging/events
- `main`: Async function called for the entry
- `schema_in`: Optional `WorkerArgs` subclass for input normalization

`main` receives:
- A `WorkerArgs` instance when `schema_in` is provided
- Otherwise, a list of prompt parts (`list[PromptContent]`)

Note: Entry functions are trusted code, but agent calls still go through approval
wrappers and follow the run approval policy. To skip prompts, use `approve_all`
(or drop to raw Python to bypass the tool plane).

Example with custom input schema:

```python
from llm_do.runtime import EntrySpec, WorkerArgs, PromptContent, WorkerRuntime

class TaggedInput(WorkerArgs):
    input: str
    tag: str

    def prompt_messages(self) -> list[PromptContent]:
        return [f"{self.input}:{self.tag}"]

async def main(args: TaggedInput, _runtime: WorkerRuntime) -> str:
    return args.tag

ENTRY_SPEC = EntrySpec(
    name="main",
    main=main,
    schema_in=TaggedInput,
)
```

---

## Writing Toolsets

Toolsets provide tools to workers. There are two approaches:

### FunctionToolset (Decorator-Based)

The simplest way to create tools. Define functions with the `@tools.tool` decorator:

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_calc_tools(_ctx):
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

    return calc_tools

calc_tools = ToolsetSpec(factory=build_calc_tools)
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

Factories receive a `ToolsetBuildContext` with worker name/path metadata if you
need to specialize per worker (e.g., base paths).

**Accessing the Runtime:**

To call other agents from your tool, accept `RunContext[WorkerRuntime]`:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import WorkerRuntime

def build_calc_tools(_ctx):
    calc_tools = FunctionToolset()

    @calc_tools.tool
    async def analyze(ctx: RunContext[WorkerRuntime], text: str) -> str:
        """Analyze text using another agent."""
        return await ctx.deps.call_agent("sentiment_analyzer", {"input": text})

    return calc_tools
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

Register it with a factory so each call gets a fresh instance:

```python
from llm_do.runtime import ToolsetSpec

def build_my_toolset(_ctx):
    return MyToolset(config={"require_approval": True})

my_toolset = ToolsetSpec(factory=build_my_toolset)
```

### Toolset Configuration

Toolset configuration lives in the toolset factory in Python. Worker YAML
only references toolset names, so you define any config when building
the toolset in a `.py` file:

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec
from llm_do.toolsets import FileSystemToolset

def build_calc_tools(_ctx):
    return FunctionToolset()

def build_filesystem(_ctx):
    return FileSystemToolset(config={"base_path": "./data", "write_approval": True})

calc_tools = ToolsetSpec(factory=build_calc_tools)
filesystem_data = ToolsetSpec(factory=build_filesystem)
```

Then reference the toolset names in your worker:

```yaml
toolsets:
  - calc_tools
  - filesystem_data
```

If you need to pre-approve specific tools, attach an approval config dict:

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.toolsets.approval import set_toolset_approval_config

def build_calc_tools(_ctx):
    tools = FunctionToolset()
    set_toolset_approval_config(
        tools,
        {
            "add": {"pre_approved": True},
            "multiply": {"pre_approved": True},
        },
    )
    return tools
```

**Dependencies:**

Toolset instances are created per call in Python, so pass any dependencies directly in
the factory (e.g., base paths, worker metadata, or sandbox handles).

### Built-in Toolsets

`filesystem_project` uses the project root passed to `build_entry` (the manifest
directory in the CLI).

| Name | Class | Tools |
|------|-------|-------|
| `filesystem_cwd` | `FileSystemToolset` | `read_file`, `write_file`, `list_files` (base: CWD) |
| `filesystem_cwd_ro` | `ReadOnlyFileSystemToolset` | `read_file`, `list_files` (base: CWD) |
| `filesystem_project` | `FileSystemToolset` | `read_file`, `write_file`, `list_files` (base: project root) |
| `filesystem_project_ro` | `ReadOnlyFileSystemToolset` | `read_file`, `list_files` (base: project root) |
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
| `name` | Yes | Worker identifier (used for `ctx.deps.call_agent()`) |
| `description` | No | Tool description when the worker is exposed as a tool (falls back to `instructions`) |
| `model` | No | Model identifier (e.g., `anthropic:claude-haiku-4-5`); falls back to `LLM_DO_MODEL` if omitted |
| `compatible_models` | No | List of acceptable model patterns for the `LLM_DO_MODEL` fallback (mutually exclusive with `model`) |
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

Use `compatible_models` when you want the worker to accept the `LLM_DO_MODEL`
fallback if it matches a pattern, rather than hardcoding `model`. Patterns use glob matching:

```yaml
compatible_models:
  - "*"                       # allow any model
  - "anthropic:*"             # any Anthropic model
  - "anthropic:claude-haiku-*"  # any Claude Haiku variant
```

Compatibility checks apply to string model IDs and `Model` objects (Python API),
and they run once at worker construction time against the env fallback.
If you set `compatible_models`, ensure `LLM_DO_MODEL` is set to a compatible value.

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
# Run a manifest
llm-do project.json "prompt"

# Run with input JSON
llm-do project.json --input-json '{"input": "prompt"}'

# Set fallback model via env var
LLM_DO_MODEL=anthropic:claude-haiku-4-5 llm-do project.json "prompt"

# TUI / headless output
llm-do project.json --tui
llm-do project.json --headless "prompt"

# Verbose output
llm-do project.json -v "prompt"      # basic
llm-do project.json -vv "prompt"     # detailed
```

See [cli.md](cli.md) for full CLI documentation.
