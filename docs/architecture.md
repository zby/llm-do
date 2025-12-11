# Architecture

This document covers the internal architecture of llm-do: runtime API, sandbox system, tool approval, and dependency injection patterns.

## Module Structure

```
llm_do/
├── runtime.py           # Worker execution and delegation
├── execution.py         # Agent execution strategies
├── model_compat.py      # Model compatibility validation
├── program.py           # Program detection and configuration
├── toolset_loader.py    # Dynamic toolset loading factory
├── types.py             # Type definitions and data models
├── protocols.py         # Protocol definitions (FileSandbox)
├── worker_sandbox.py    # Sandbox extension for llm-do
├── registry.py          # Worker definition loading/persistence
├── shell/               # Shell toolset package
│   ├── __init__.py      # Package exports
│   ├── execution.py     # Shell command execution
│   ├── toolset.py       # PydanticAI toolset wrapper
│   └── types.py         # Shell-specific types
├── ui/                  # Display and UI components
│   ├── __init__.py      # Package exports
│   └── display.py       # Display backend abstractions
├── delegation_toolset.py # Worker delegation toolset
├── custom_toolset.py    # Custom Python tools toolset
├── cli.py               # Sync CLI (init, programmatic use)
└── cli_async.py         # Async CLI entry point (default)
```

**External packages** (extracted for reuse):
- `pydantic-ai-blocking-approval` — Synchronous tool approval system
- `pydantic-ai-filesystem-sandbox` — Sandboxed file operations toolset

---

## Runtime API

### Entry Points

#### run_worker / run_worker_async

Primary entry points for executing workers.

```python
from llm_do import run_worker, run_worker_async

# Sync version
result = run_worker(
    registry=registry,
    worker="my-worker",
    input_data={"task": "..."},
    attachments=None,
    cli_model="openai:gpt-4",
    approval_controller=controller,
    message_callback=on_message,
)

# Async version (recommended for nested worker calls)
result = await run_worker_async(...)
```

**Returns:** `WorkerRunResult` with `output` and `messages`.

#### call_worker / call_worker_async

Delegate to another worker (used internally by `worker_call` tool).

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
- `allow_workers` allowlist from caller's definition
- `compatible_models` validation (caller's model must match target worker's patterns)
- Attachment approval via sandbox with full metadata
- Attachment policy limits (max count, total size, allowed suffixes)

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

Workers are saved to `workers/generated/{name}/worker.worker`.

### WorkerContext

Runtime context passed to worker execution and available to tools via PydanticAI's dependency injection.

```python
@dataclass
class WorkerContext:
    registry: WorkerRegistry
    worker: WorkerDefinition
    attachment_validator: AttachmentValidator
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController
    sandbox: Optional[Sandbox]
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

## Sandbox System

### Two-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    llm-do Sandbox                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Sandbox (from pydantic-ai-filesystem-sandbox)│ │
│  │                                                        │ │
│  │  Boundaries: readable_roots, writable_roots            │ │
│  │  Query API: can_read(), can_write(), resolve()         │ │
│  │  LLM-friendly errors guide correction                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           FileSystemToolset (wrapped with approval)    │ │
│  │                                                        │ │
│  │  Tools: read_file, write_file, edit_file, list_files   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  llm-do extensions:                                          │
│    network_enabled: bool                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

1. **Sandbox** (from `pydantic-ai-filesystem-sandbox`) — File access boundaries, LLM-friendly errors
2. **FileSystemToolset** — Provides file tools, wrapped with ApprovalToolset for approval gating

**Note:** For kernel-level isolation, run llm-do in a Docker container.

### Configuration

```yaml
# In worker.worker file
name: my_worker
description: A worker with file access

# Sandbox config at top level (separate from toolsets)
sandbox:
  paths:
    input:
      root: ./input
      mode: ro
      suffixes: [.pdf, .txt]
    output:
      root: ./output
      mode: rw
      write_approval: true
      max_file_bytes: 10000000

# Toolsets as class paths or aliases
toolsets:
  filesystem: {}  # FileSystemToolset - uses sandbox above
```

**PathConfig options:**
- `root` — Directory path
- `mode` — `ro` (read-only) or `rw` (read-write)
- `suffixes` — Allowed file extensions (e.g., `[.md, .pdf]`)
- `max_file_bytes` — Maximum file size limit
- `write_approval` — Require approval for writes (default: true)
- `read_approval` — Require approval for reads (default: false)

### Available Tools

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read text file from sandbox |
| `write_file(path, content)` | Write text file to sandbox |
| `edit_file(path, old_text, new_text)` | Search/replace in file |
| `list_files(path, pattern)` | List files matching glob pattern |

### Error Classes

Error messages guide the LLM to correct behavior:

```python
PathNotInSandboxError
# "Cannot access '{path}': path is outside sandbox. Readable paths: {roots}"

PathNotWritableError
# "Cannot write to '{path}': path is read-only. Writable paths: {roots}"

SuffixNotAllowedError
# "Cannot access '{path}': suffix not allowed. Allowed: {suffixes}"

FileTooLargeError
# "Cannot read '{path}': file too large. Maximum: {limit} bytes"

EditError
# "Cannot edit '{path}': text not found in file."
```

---

## Toolset System

Workers declare toolsets in their definition. The `toolset_loader.py` module dynamically loads and wraps them.

### Configuration

```yaml
# worker.worker file
name: my_worker
sandbox:
  paths:
    data: {root: ./data, mode: rw}

toolsets:
  # Built-in aliases
  filesystem: {}           # File I/O tools (requires sandbox)
  shell:                   # Shell commands (sandbox optional)
    rules:
      - pattern: "git *"
        approval_required: false
  delegation:              # Worker delegation
    allow_workers: [helper]
  custom:                  # Custom Python tools from tools.py
    my_tool: {}

  # Or full class paths for third-party toolsets
  mycompany.toolsets.DatabaseToolset:
    connection_string: "..."
```

### Built-in Aliases

| Alias | Class Path | Requires |
|-------|-----------|----------|
| `filesystem` | `pydantic_ai_filesystem_sandbox.FileSystemToolset` | sandbox |
| `shell` | `llm_do.shell.toolset.ShellToolset` | - |
| `delegation` | `llm_do.delegation_toolset.DelegationToolset` | - |
| `custom` | `llm_do.custom_toolset.CustomToolset` | tools.py |

### Toolset Loading

All toolsets are wrapped with `ApprovalToolset` for unified approval handling:

```python
# toolset_loader.py
def create_toolset(class_path, config, context, ...):
    toolset_class = _import_class(class_path)

    # FileSystemToolset needs sandbox in constructor (external package)
    if class_path == "filesystem":
        toolset = toolset_class(sandbox=context.sandbox)
    else:
        # All others: config in constructor, ctx.deps at runtime
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

The sandbox's file tools are wrapped with `ApprovalToolset` from `pydantic-ai-blocking-approval`:

```python
from pydantic_ai_filesystem_sandbox import FileSystemToolset
from pydantic_ai_blocking_approval import ApprovalToolset

file_toolset = FileSystemToolset(sandbox=sandbox)
approved = ApprovalToolset(
    inner=file_toolset,
    approval_callback=controller.approval_callback,
    memory=controller.memory,
)
agent = Agent(..., toolsets=[approved])
```

This respects `PathConfig.write_approval` and `PathConfig.read_approval` settings.

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
| `write_file` / `edit_file` | `PathConfig.write_approval: true` |
| `read_file` (for attachments) | `PathConfig.read_approval: true` |
| `shell` | `toolsets.shell.rules` match or `toolsets.shell.default.approval_required` |
| `worker_call` | Always (controller mode determines behavior) |
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
    sandbox = ctx.deps.sandbox
    registry = ctx.deps.registry
    ...
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
        sandbox = ctx.deps.sandbox
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
CLI / run_worker()
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
│ Sandbox         │ ← Create sandbox from config
│ + ApprovalWrap  │
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
| `shell/` | ~350 | Shell toolset package (whitelist-based approval) |
| `delegation_toolset.py` | ~150 | Worker delegation toolset |
| `custom_toolset.py` | ~150 | Custom Python tools toolset |
| `worker_sandbox.py` | ~250 | Sandbox extension, attachment validation |
| `protocols.py` | ~100 | Interface definitions for DI |
| `types.py` | ~200 | Data models (WorkerDefinition, WorkerContext) |
| `registry.py` | ~200 | Worker loading and persistence |
