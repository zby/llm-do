# Architecture

This document covers the internal architecture of llm-do: runtime API, toolset system, tool approval, attachment handling, and dependency injection patterns.

## Module Structure

```
llm_do/
├── runtime.py           # Worker execution and delegation
├── execution.py         # Agent execution strategies
├── model_compat.py      # Model compatibility validation
├── toolset_loader.py    # Dynamic toolset loading factory
├── types.py             # Type definitions and data models
├── registry.py          # Worker definition loading/persistence
├── attachments/         # Attachment policy and payload types
├── filesystem_toolset.py # File I/O tools (container boundary)
├── delegation_toolset.py # Worker delegation toolset (_worker_* tools)
├── custom_toolset.py    # Custom Python tools toolset
├── shell/               # Shell toolset package
│   ├── __init__.py      # Package exports
│   ├── execution.py     # Shell command execution
│   ├── toolset.py       # PydanticAI toolset wrapper
│   └── types.py         # Shell-specific types
├── ui/                  # Display and UI components
│   ├── __init__.py      # Package exports
│   └── display.py       # Display backend abstractions
├── cli_async.py         # Async CLI entry point (default)
└── base.py              # Public API exports
```

**External packages** (extracted for reuse):
- `pydantic-ai-blocking-approval` — Synchronous tool approval system

---

## Runtime API

### Entry Points

#### run_worker_async

Primary entry point for executing workers.

```python
from llm_do import run_worker_async

result = await run_worker_async(
    registry=registry,
    worker="my-worker",
    input_data={"task": "..."},
    attachments=None,
    cli_model="openai:gpt-4",
    approval_controller=controller,
    message_callback=on_message,
)
```

**Returns:** `WorkerRunResult` with `output` and `messages`.

#### call_worker_async

Delegate to another worker (used internally by the delegation toolset and `ToolContext`).

```python
result = await call_worker_async(
    registry=registry,
    worker="target-worker",
    input_data=payload,
    caller_context=context,
    attachments=files,
)
```

**Enforces:**
- `compatible_models` validation (target worker's patterns)
- Attachment policy limits (max count, total size, allowed suffixes)
- Max worker depth (recursion protection)

#### create_worker

Create and persist a new worker definition.

```python
from llm_do import create_worker, WorkerSpec

spec = WorkerSpec(
    name="new-worker",
    instructions="You are a helpful assistant.",
    description="A simple worker",
)

definition = create_worker(registry=registry, spec=spec, defaults=defaults)
```

Workers are saved to the generated directory (e.g., `generated/{name}/worker.worker`).

### WorkerContext

Runtime context passed to worker execution and available to tools via PydanticAI's dependency injection.

```python
@dataclass
class WorkerContext:
    worker: WorkerDefinition
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController
    depth: int = 0
    cost_tracker: Optional[Any] = None
    registry: WorkerRegistry
    creation_defaults: WorkerCreationDefaults
    attachments: List[AttachmentPayload]
    message_callback: Optional[MessageCallback]
    custom_tools_path: Optional[Path]
```

Tools access context via `RunContext[WorkerContext]`:

```python
from pydantic_ai import RunContext
from llm_do import WorkerContext

@agent.tool
def my_tool(ctx: RunContext[WorkerContext], arg: str) -> str:
    worker_name = ctx.deps.worker.name
    # ...
```

---

## Filesystem Toolset

llm-do ships a simple filesystem toolset (`llm_do.filesystem_toolset.FileSystemToolset`)
that operates on normal paths (relative to CWD or absolute). There is no path sandboxing;
use a container boundary for isolation.

### Configuration

```yaml
toolsets:
  filesystem:
    read_approval: false
    write_approval: true
```

### Available Tools

| Tool | Description |
|------|-------------|
| `read_file(path, max_chars?, offset?)` | Read UTF-8 text files (use attachments for binary) |
| `write_file(path, content)` | Write text files |
| `list_files(path, pattern)` | List files matching a glob |

### Errors

`read_file` and `write_file` raise standard filesystem exceptions (e.g.,
`FileNotFoundError`, `IsADirectoryError`, `UnicodeDecodeError`).

---

## Toolset System

Workers declare toolsets in their definition. The `toolset_loader.py` module dynamically loads and wraps them.

### Configuration

```yaml
# worker.worker file
name: my_worker

toolsets:
  # Built-in aliases
  filesystem:
    read_approval: false
    write_approval: true
  shell:
    rules:
      - pattern: "git *"
        approval_required: false
  delegation:              # Worker delegation (tool map: worker name → config)
    helper: {}             # Creates _worker_helper tool
    worker_create: {}      # Creates worker_create tool
  custom:                  # Custom Python tools from tools.py
    my_tool: {}

  # Or full class paths for third-party toolsets
  mycompany.toolsets.DatabaseToolset:
    connection_string: "..."
```

### Built-in Aliases

| Alias | Class Path | Requires |
|-------|-----------|----------|
| `filesystem` | `llm_do.filesystem_toolset.FileSystemToolset` | - |
| `shell` | `llm_do.shell.toolset.ShellToolset` | - |
| `delegation` | `llm_do.delegation_toolset.DelegationToolset` | - |
| `custom` | `llm_do.custom_toolset.CustomToolset` | tools.py |

### Toolset Loading

All toolsets are wrapped with `ApprovalToolset` for unified approval handling:

```python
# toolset_loader.py
def create_toolset(class_path, config, context, ...):
    toolset_class = _import_class(class_path)

    # All toolsets receive config, ctx.deps at runtime
    toolset = toolset_class(config=config)

    return ApprovalToolset(inner=toolset, ...)
```

### Future: REQUIRED_DEPS Validation

Toolsets could declare required dependencies for early validation:

```python
class CustomToolset(AbstractToolset):
    REQUIRED_DEPS = ["custom_tools_path"]  # Validate at creation time
```

This would fail fast if a required dep (like `custom_tools_path` for custom toolset) is missing, rather than failing at runtime.

---

## Tool Approval System

The approval system uses `pydantic-ai-blocking-approval` (v0.4.0+) for synchronous, blocking approval workflows.

### Core Types

```python
from pydantic_ai_blocking_approval import (
    ApprovalController,    # Mode manager (interactive/approve_all/strict)
    ApprovalDecision,      # User decision (approved, note, remember)
    ApprovalMemory,        # Session cache
    ApprovalRequest,       # Request for approval (tool_name, tool_args, description)
    ApprovalToolset,       # Wrapper for toolsets
)
```

### ApprovalController Modes

```python
# Interactive mode - prompts user via callback
controller = ApprovalController(
    mode="interactive",
    approval_callback=my_callback,
)

# Auto-approve mode - for tests
controller = ApprovalController(mode="approve_all")

# Strict mode - rejects all approval-required operations
controller = ApprovalController(mode="strict")
```

| Mode | Behavior |
|------|----------|
| `interactive` | Prompts user via callback |
| `approve_all` | Auto-approves all requests |
| `strict` | Auto-denies all requests |

### FileSystemToolset with Approval

The filesystem toolset implements `needs_approval()` based on its config:

```python
from llm_do.filesystem_toolset import FileSystemToolset
from pydantic_ai_blocking_approval import ApprovalToolset

file_toolset = FileSystemToolset(config={
    "read_approval": False,
    "write_approval": True,
})
approved = ApprovalToolset(
    inner=file_toolset,
    approval_callback=controller.approval_callback,
    memory=controller.memory,
)
agent = Agent(..., toolsets=[approved])
```

This respects `read_approval` and `write_approval` settings from `toolsets.filesystem`.

### Custom Tool Approval

**Secure by default**: All custom tools require approval. `CustomToolset` uses config-based approval via the `ApprovalToolset` wrapper (it doesn't implement `needs_approval()` itself):

```python
# ApprovalToolset wraps CustomToolset with config-based approval
approved = ApprovalToolset(
    inner=custom_toolset,
    approval_callback=callback,
    config={
        "my_safe_tool": {"pre_approved": True},
        # All other tools require approval (secure by default)
    },
)
```

### Shell Tool Approval

Shell commands use a **whitelist model** configured under `toolsets.shell`:

```yaml
toolsets:
  shell:
    rules:
      - pattern: "git status"
        approval_required: false  # Pre-approved
      - pattern: "git commit"
        approval_required: true   # Requires approval
      # rm -rf is NOT in rules = blocked
    default:
      approval_required: true  # Unmatched commands allowed with approval
      # Omit default entirely to block all unmatched commands
```

**Whitelist semantics:**
- Command matches a rule → allowed (with rule's `approval_required`)
- No rule matches but `default` exists → allowed (with default's `approval_required`)
- No rule matches and no `default` → **blocked**

### Approval Configuration Summary

| Tool | Approval Trigger |
|------|------------------|
| `write_file` | `toolsets.filesystem.write_approval: true` |
| `read_file` | `toolsets.filesystem.read_approval: true` |
| `shell` | `toolsets.shell.rules` match or `toolsets.shell.default.approval_required` |
| `_worker_*` (delegation) | Always (controller mode determines behavior) |
| `worker_create` | Always (controller mode determines behavior) |
| Custom tools | Always (secure by default) |

---

## Dependency Injection

llm-do uses PydanticAI's built-in dependency injection via `ctx.deps`:

```python
agent = Agent(model=..., deps_type=WorkerContext)
result = await agent.run(input_data, deps=context)

# Tools access runtime context via ctx.deps
@agent.tool
async def my_tool(ctx: RunContext[WorkerContext], path: str):
    registry = ctx.deps.registry
    attachments = ctx.deps.attachments
    ...
```

Tools that need nested worker calls depend on `ToolContext`:

```python
from llm_do import ToolContext

@agent.tool
async def orchestrate(ctx: RunContext[ToolContext], task: str) -> str:
    return await ctx.deps.call_worker("reviewer", task)
```

### Toolset Pattern

Toolsets receive `config` in constructor and access runtime deps via `ctx.deps`:

```python
from pydantic_ai_blocking_approval import ApprovalResult

class MyToolset(AbstractToolset[WorkerContext]):
    def __init__(self, config: dict):
        self._config = config

    async def call_tool(self, name, tool_args, ctx, tool):
        # Access runtime deps at call time
        registry = ctx.deps.registry
        ...

    def needs_approval(self, name: str, tool_args: dict, ctx: RunContext) -> ApprovalResult:
        """Return approval status for tool call."""
        if self._is_blocked(name, tool_args):
            return ApprovalResult.blocked("Reason for blocking")
        if self._is_pre_approved(name, tool_args):
            return ApprovalResult.pre_approved()
        return ApprovalResult.needs_approval()

    def get_approval_description(self, name: str, tool_args: dict, ctx: RunContext) -> str:
        """Return human-readable description for approval prompt."""
        return f"Execute {name} with {tool_args}"
```

This achieves:
- Simple, consistent pattern across all toolsets
- Runtime deps available where needed (not constructor-injected)
- Testability (mock ctx.deps in tests)
- Clean separation: `needs_approval()` for decision, `get_approval_description()` for presentation

---

## Execution Flow

```
CLI / run_worker_async()
        │
        ▼
┌─────────────────┐
│ WorkerRegistry  │ ← Load worker definition
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WorkerContext   │ ← Build execution context
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Toolsets        │ ← Build toolsets + approval wrappers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PydanticAI      │ ← Create agent with tools
│ Agent           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ agent.run()     │ ← Execute with deps=context
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ WorkerRunResult │ ← Return output + messages
└─────────────────┘
```

---

## Key Files

| File | Lines | Responsibility |
|------|-------|----------------|
| `runtime.py` | ~540 | Worker orchestration, delegation, creation |
| `execution.py` | ~280 | Agent execution, ApprovalToolset wrapping |
| `model_compat.py` | ~180 | Model compatibility validation |
| `toolset_loader.py` | ~120 | Toolset loading and wrapping |
| `shell/` | ~350 | Shell toolset package (whitelist-based approval) |
| `delegation_toolset.py` | ~400 | Worker delegation toolset |
| `filesystem_toolset.py` | ~200 | File I/O toolset (container boundary) |
| `custom_toolset.py` | ~150 | Custom Python tools toolset |
| `attachments/` | ~120 | Attachment policy and payload types |
| `types.py` | ~200 | Data models (WorkerDefinition, WorkerContext) |
| `registry.py` | ~200 | Worker loading and persistence |
