# Reference

API and usage reference for llm-do. For theory, see [theory.md](theory.md). For internals, see [architecture.md](architecture.md).

---

## Agent Input Schemas

Agent files (`.agent`) can declare a Pydantic input schema so agent calls (and tool-call
planning) use a structured contract:

```yaml
---
name: evaluator
schema_in_ref: schemas.py:PitchInput
---
```

Supported forms:
- `module.Class`
- `path.py:Class` (relative to the agent file)

Schemas must subclass `AgentArgs` and implement `prompt_messages()`. Input can be passed in several forms:

```python
# Simple string
await ctx.deps.call_agent("agent_name", "text")

# With attachments
await ctx.deps.call_agent("agent_name", {"input": "text", "attachments": ["file.pdf"]})
```

For custom schemas, subclass `AgentArgs`:

```python
from llm_do.runtime import PromptContent, AgentArgs

class PitchInput(AgentArgs):
    input: str
    company_name: str

    def prompt_messages(self) -> list[PromptContent]:
        return [f"Evaluate {self.company_name}: {self.input}"]
```

This schema shapes tool-call arguments and validates inputs before the agent runs.

## Entry Selection

Entry selection is explicit in the manifest:
- `entry.agent` selects an agent name from `.agent` files (runs as an AgentEntry)
- `entry.function` selects a Python function via `path.py:function` (must be listed in `python_files`) and wraps it as a FunctionEntry

If the target cannot be resolved, loading fails with a descriptive error.

## Calling Agents from Python

Python code can invoke agents in two contexts:
1. **From entry functions** — using `ctx.call_agent()` directly on the `CallContext`
2. **From within tools** — using `ctx.deps.call_agent()` where `ctx.deps` is the `CallContext`

### call_agent API

```python
async def call_agent(spec_or_name: AgentSpec | str, input_data: Any) -> Any
```

Invokes an agent by name (looked up in the registry) or by `AgentSpec` directly.

**Parameters:**
- `spec_or_name`: Agent name (string) or `AgentSpec` instance
- `input_data`: Input payload—can be:
  - `str`: Simple text input
  - `dict`: With `"input"` key and optional `"attachments"` list
  - `list`: Prompt parts (strings and `Attachment` objects)
  - `AgentArgs`: Custom schema instance

**Returns:** The agent's output (typically a string)

**Raises:** `RuntimeError` if `max_depth` is exceeded

**Example:**
```python
# From entry function
async def main(input_data, ctx: CallContext) -> str:
    result = await ctx.call_agent("analyzer", {"input": "data"})
    return result

# From tool
@tools.tool
async def my_tool(ctx: RunContext[CallContext], data: str) -> str:
    return await ctx.deps.call_agent("analyzer", data)
```

If you pass an `AgentSpec` directly, its `model` must already be a resolved `Model`
instance. Use `resolve_model(...)` (or pass a PydanticAI model object):

```python
from llm_do import resolve_model
from llm_do.runtime import AgentSpec

spec = AgentSpec(
    name="analyzer",
    instructions="Analyze input.",
    model=resolve_model("anthropic:claude-haiku-4-5"),
)
result = await ctx.deps.call_agent(spec, "input text")
```

### Starting a Run (Runtime.run_entry)

Use `Runtime` to create a shared execution environment and run an entry:

```python
from pathlib import Path

from llm_do.runtime import (
    EntryConfig,
    Runtime,
    RunApprovalPolicy,
    build_registry,
    resolve_entry,
)

async def main():
    project_root = Path(".").resolve()
    registry = build_registry(
        ["analyzer.agent"],
        [],
        project_root=project_root,
    )
    entry = resolve_entry(
        EntryConfig(agent="analyzer"),
        registry,
        python_files=[],
        base_path=project_root,
    )
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        project_root=project_root,
    )
    runtime.register_agents(registry.agents)

    result, ctx = await runtime.run_entry(
        entry,
        input_data="Analyze this data",
    )

    print(result)
```

`Runtime.run_entry()`:
- Creates a fresh entry runtime (NullModel, no toolsets) for the entry function
- Reuses runtime-scoped state (usage, approval cache, message log)
- Runtime state is process-scoped (in-memory only, not persisted beyond the process)
- Returns both the result and the runtime context
 
`build_registry()` returns an `AgentRegistry` and requires an explicit `project_root`; `AgentRegistry` is a thin
container around the `agents` mapping, so pass the same root to `Runtime` and register `registry.agents` to keep
filesystem toolsets and attachment resolution aligned.

Agent files resolve model identifiers when building the registry (or when dynamic
agents are created). `AgentSpec.model` always stores a resolved `Model` instance.
Entry functions run under NullModel (no toolsets), so direct LLM calls from entry
code are not allowed.

**Parameters:**

| Parameter | Description |
|-----------|-------------|
| `entry` | `Entry` to run (AgentEntry or FunctionEntry) |
| `input_data` | Input payload (str, list of prompt parts, dict, or `AgentArgs`) |
| `message_history` | Pre-seed conversation history for the top-level call scope |

Use `Runtime.run()` for sync execution when you already have an entry object.

### Multi-Turn Entries (message_history)

For chat-style flows, carry forward `message_history` between turns:

```python
from pathlib import Path

from llm_do.runtime import EntryConfig, Runtime, build_registry, resolve_entry

async def main():
    project_root = Path(".").resolve()
    registry = build_registry(
        ["assistant.agent"],
        [],
        project_root=project_root,
    )
    entry = resolve_entry(
        EntryConfig(agent="assistant"),
        registry,
        python_files=[],
        base_path=project_root,
    )
    runtime = Runtime(project_root=project_root)
    runtime.register_agents(registry.agents)

    message_history = None
    result, ctx = await runtime.run_entry(entry, {"input": "turn 1"})
    message_history = list(ctx.frame.messages)

    result, ctx = await runtime.run_entry(
        entry,
        {"input": "turn 2"},
        message_history=message_history,
    )
```

The top-level agent consumes `message_history` on each turn at depth 0.

### From Within Tools

Tools can access the runtime to call other agents. This enables hybrid patterns where deterministic Python code orchestrates LLM reasoning.

**Accepting the Runtime Context:**

To access the runtime, accept `RunContext[CallContext]` as the first parameter:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec, CallContext

def build_tools():
    tools = FunctionToolset()

    @tools.tool
    async def my_tool(ctx: RunContext[CallContext], data: str) -> str:
        """Tool that can call agents."""
        result = await ctx.deps.call_agent("agent_name", data)
        return result

    return tools

tools = ToolsetSpec(factory=build_tools)
```

The `ctx` parameter is automatically injected by PydanticAI and excluded from the tool schema the LLM sees.

**Calling Agents:**

Use `ctx.deps.call_agent(spec_or_name, input_data)` to invoke an agent by name or `AgentSpec`:

```python
@tools.tool
async def orchestrate(ctx: RunContext[CallContext], task: str) -> str:
    # Call an LLM agent
    analysis = await ctx.deps.call_agent("analyzer", task)
    return analysis
```

`RunContext.prompt` is derived from `AgentArgs.prompt_messages()` for logging/UI
only; tools should rely on their typed args and use `ctx.deps` only for delegation.

The `input_data` argument can be a string, list (with `Attachment`s), dict, or `AgentArgs`.

**Available Runtime State:**

Via `ctx.deps` (a `CallContext`), tools can access:

| Property | Description |
|----------|-------------|
| `call_agent(spec_or_name, input_data)` | Invoke an agent by name or `AgentSpec` |
| `frame.config.depth` | Current nesting depth |
| `frame.config.model` | Resolved `Model` instance for this call |
| `frame.prompt` | Current prompt string |
| `frame.messages` | Conversation history |
| `config.max_depth` | Maximum allowed depth |
| `config.project_root` | Project root path |

### Example: Code Entry Point

A common pattern is using a Python function as the entry point for deterministic orchestration:

```python
from pathlib import Path

from llm_do.runtime import CallContext

async def main(_input_data, runtime: CallContext) -> str:
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

```

Run with a manifest that includes `tools.py` and `evaluator.agent`, and set:
`entry.function: "tools.py:main"` in `project.json`.

If you want to create the entry manually (outside the manifest flow), wrap it:
`FunctionEntry(name="main", fn=main)`.

`FunctionEntry` fields:
- `name`: Entry name for logging/events
- `fn`: Async function called for the entry
- `schema_in`: Optional `AgentArgs` subclass for input normalization

Convenience helper:
- `FunctionEntry.from_function(fn)` creates an entry using `fn.__name__` as the name.

The entry function receives:
- A `AgentArgs` instance when `schema_in` is provided
- Otherwise, a list of prompt parts (`list[PromptContent]`)

Note: Entry functions are trusted code, but agent calls still go through approval
wrappers and follow the run approval policy. To skip prompts, use `approve_all`
(or drop to raw Python to bypass the tool plane).

Example with custom input schema:

```python
from llm_do.runtime import FunctionEntry, AgentArgs, PromptContent, CallContext

class TaggedInput(AgentArgs):
    input: str
    tag: str

    def prompt_messages(self) -> list[PromptContent]:
        return [f"{self.input}:{self.tag}"]

async def main(args: TaggedInput, _runtime: CallContext) -> str:
    return args.tag

ENTRY = FunctionEntry(
    name="main",
    fn=main,
    schema_in=TaggedInput,
)
```

---

## Stabilizing Workflow

Stabilize stochastic components to deterministic code as patterns emerge.

### 1. Start stochastic

Agent handles everything with LLM judgment:

```yaml
---
name: filename_cleaner
model: anthropic:claude-haiku-4-5
---
Clean the given filename: remove special characters,
normalize spacing, ensure valid extension.
```

### 2. Observe patterns

Run it repeatedly. Watch what the LLM consistently does:
- Always lowercases
- Replaces spaces with underscores
- Strips leading/trailing whitespace
- Keeps alphanumerics and `.-_`

### 3. Extract to code

Stable patterns become Python:

```python
@tools.tool
def sanitize_filename(name: str) -> str:
    """Remove special characters from filename."""
    name = name.strip().lower()
    return "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)
```

### 4. Keep stochastic edges

Agent still handles ambiguous cases the code can't:

```yaml
---
name: filename_cleaner
model: anthropic:claude-haiku-4-5
toolsets: [filename_tools]
---
Clean the given filename. Use sanitize_filename for basic cleanup.
For ambiguous cases (is "2024-03" a date or version?), use judgment
to pick the most descriptive format.
```

### What changes when you stabilize

| Aspect | Before (stochastic) | After (deterministic) |
|--------|---------------------|----------------------|
| Cost | Per-token API charges | Effectively free |
| Latency | Network + inference | Microseconds |
| Reliability | May vary | Identical every time |
| Testing | Statistical sampling | Assert equality |
| Approvals | May need user consent | Trusted by default |

### Canonical progression

The pitchdeck examples demonstrate this:

1. **[`pitchdeck_eval/`](../examples/pitchdeck_eval/)** — All LLM: orchestrator decides everything
2. **[`pitchdeck_eval_stabilized/`](../examples/pitchdeck_eval_stabilized/)** — Extracted `list_pitchdecks()` to Python
3. **[`pitchdeck_eval_code_entry/`](../examples/pitchdeck_eval_code_entry/)** — Python orchestration, LLM only for analysis

---

## Softening Workflow

Soften deterministic code back to stochastic when edge cases multiply or you need new capability.

### Extension (common)

Need new capability? Write a spec:

```yaml
---
name: sentiment_analyzer
model: anthropic:claude-haiku-4-5
---
Analyze the sentiment of the given text.
Return: positive, negative, or neutral with confidence score.
```

Now it's callable:

```python
result = await ctx.deps.call_agent("sentiment_analyzer", {"input": feedback})
```

### Replacement (rare)

Rigid code drowning in edge cases? A function full of `if/elif` handling linguistic variations might be better as an LLM call that handles the variation naturally.

### Hybrid pattern

Python handles deterministic logic; agents handle judgment:

```python
@tools.tool
async def evaluate_document(ctx: RunContext[CallContext], path: str) -> dict:
    content = load_file(path)           # deterministic
    if not validate_format(content):    # deterministic
        raise ValueError("Invalid format")

    # Stochastic: LLM judgment for analysis
    analysis = await ctx.deps.call_agent("content_analyzer", {"input": content})

    return {                            # deterministic
        "score": compute_score(analysis),
        "analysis": analysis
    }
```

Think: "deterministic pipeline that uses LLM where judgment is needed."

---

## Writing Toolsets

Toolsets provide tools to agents. There are two approaches:

### FunctionToolset (Decorator-Based)

The simplest way to create tools. Define functions with the `@tools.tool` decorator:

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec

def build_calc_tools():
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

Save as `tools.py` and reference in your agent:

```yaml
---
name: calculator
model: anthropic:claude-haiku-4-5
toolsets:
  - calc_tools
---
You are a helpful calculator...
```

Factories take no arguments; close over any configuration you need when
defining the factory (e.g., base paths).

**Accessing the Runtime:**

To call other agents from your tool, accept `RunContext[CallContext]`:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import CallContext

def build_calc_tools():
    calc_tools = FunctionToolset()

    @calc_tools.tool
    async def analyze(ctx: RunContext[CallContext], text: str) -> str:
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

def build_my_toolset():
    return MyToolset(config={"require_approval": True})

my_toolset = ToolsetSpec(factory=build_my_toolset)
```

### Toolset Configuration

Toolset configuration lives in the toolset factory in Python. Agent YAML
only references toolset names, so you define any config when building
the toolset in a `.py` file:

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.runtime import ToolsetSpec
from llm_do.toolsets import FileSystemToolset

def build_calc_tools():
    return FunctionToolset()

def build_filesystem():
    return FileSystemToolset(config={"base_path": "./data", "write_approval": True})

calc_tools = ToolsetSpec(factory=build_calc_tools)
filesystem_data = ToolsetSpec(factory=build_filesystem)
```

Then reference the toolset names in your agent:

```yaml
toolsets:
  - calc_tools
  - filesystem_data
```

If you need to pre-approve specific tools, attach an approval config dict:

```python
from pydantic_ai.toolsets import FunctionToolset
from llm_do.toolsets.approval import set_toolset_approval_config

def build_calc_tools():
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
the factory (e.g., base paths or sandbox handles).

### Built-in Toolsets

`filesystem_project` uses the project root passed to `build_registry` (the manifest
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

## Agent File Format

Agents are defined in `.agent` files with YAML frontmatter:

```yaml
---
name: my_agent
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
| `name` | Yes | Agent identifier (used for `ctx.deps.call_agent()`) |
| `description` | No | Tool description when the agent is exposed as a tool (falls back to `instructions`) |
| `model` | No | Model identifier (e.g., `anthropic:claude-haiku-4-5`), resolved on load; falls back to `LLM_DO_MODEL` if omitted |
| `compatible_models` | No | List of acceptable model patterns for the `LLM_DO_MODEL` fallback (mutually exclusive with `model`) |
| `schema_in_ref` | No | Input schema reference (see [Agent Input Schemas](#agent-input-schemas)) |
| `server_side_tools` | No | Server-side tool configs (e.g., web search) |
| `toolsets` | No | List of toolset names |

**Model Format:**

Models use the format `provider:model-name`:
- `anthropic:claude-haiku-4-5`
- `openai:gpt-4o-mini`
- `ollama:llama3`

When constructing `AgentSpec` in Python, use `resolve_model("provider:model-name")`
to turn these identifiers into `Model` instances.

**Custom Providers:**

To use a custom provider with `LLM_DO_MODEL`, register a model factory in a Python file that gets
imported when your project loads (e.g., add it to `python_files` in `project.json`):

```python
# providers.py
from pydantic_ai.models.openai import OpenAIChatModel

from llm_do import register_model_factory
from llm_do.providers import OpenAICompatibleProvider

class AcmeProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(
            base_url="http://127.0.0.1:11434/v1",
            name="acme",
        )

def build_acme(model_name: str) -> OpenAIChatModel:
    return OpenAIChatModel(model_name, provider=AcmeProvider())

register_model_factory("acme", build_acme)
```

Then set:

```bash
export LLM_DO_MODEL="acme:my-model"
```

**Toolset References:**

Toolsets can be specified as:
- Built-in toolset name (e.g., `filesystem_project`, `shell_readonly`)
- Toolset instance name from a Python file passed to the CLI
- Other agent names from `.agent` files (agents act as toolsets)

**Recursive Agents:**

Agents can opt into recursion by listing themselves in `toolsets`:

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

Use `compatible_models` when you want the agent to accept the `LLM_DO_MODEL`
fallback if it matches a pattern, rather than hardcoding `model`. Patterns use glob matching:

```yaml
compatible_models:
  - "*"                       # allow any model
  - "anthropic:*"             # any Anthropic model
  - "anthropic:claude-haiku-*"  # any Claude Haiku variant
```

Compatibility checks run when resolving the `LLM_DO_MODEL` fallback during
`.agent`/dynamic agent creation. If you build `AgentSpec` in Python, call
`select_model(...)` yourself if you want compatibility validation. If you set
`compatible_models`, ensure `LLM_DO_MODEL` is set to a compatible value.

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
