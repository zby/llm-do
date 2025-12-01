# Architecture

This document covers the internal architecture of llm-do: runtime API, sandbox system, tool approval, and dependency injection patterns.

## Module Structure

```
llm_do/
├── runtime.py           # Worker execution and delegation
├── execution.py         # Agent execution strategies
├── types.py             # Type definitions and data models
├── tools.py             # Tool registration
├── protocols.py         # Dependency injection protocols
├── worker_sandbox.py    # Sandbox extension for llm-do
├── registry.py          # Worker definition loading/persistence
└── cli.py               # CLI entry point
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
    shell_cwd: Optional[Path]
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
│  │           FileSandboxImpl (reusable core)              │ │
│  │                                                        │ │
│  │  Tools: read_file, write_file, edit_file, list_files   │ │
│  │  Boundaries: readable_roots, writable_roots            │ │
│  │  Query API: can_read(), can_write(), resolve()         │ │
│  │  LLM-friendly errors guide correction                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  llm-do extensions:                                          │
│    network_enabled: bool                                     │
│    require_os_sandbox: bool                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

1. **FileSandboxImpl** (from `pydantic-ai-filesystem-sandbox`) — File access boundaries, tools, LLM-friendly errors
2. **Sandbox** (llm-do specific) — Extends with network control and OS enforcement hooks

### Configuration

```yaml
# In worker.worker file
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
  network: false
  require_os_sandbox: false
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

### FileSandboxApprovalToolset

The sandbox is wrapped with `FileSandboxApprovalToolset` from `pydantic-ai-filesystem-sandbox`:

```python
from pydantic_ai_filesystem_sandbox.approval import FileSandboxApprovalToolset

approval_sandbox = FileSandboxApprovalToolset(
    inner=sandbox,
    approval_callback=controller.approval_callback,
    memory=controller.memory,
)
agent = Agent(..., toolsets=[approval_sandbox])
```

This respects `PathConfig.write_approval` and `PathConfig.read_approval` settings.

### Custom Tool Approval

**Secure by default**: All custom tools require approval. The wrapper in `tools.py` creates an `ApprovalRequest` before executing any custom tool:

```python
# In tools.py - custom tools always require approval
request = ApprovalRequest(
    tool_name=name,
    tool_args=tool_kwargs,
    description=f"Custom tool: {name}",
)
decision = ctx.deps.approval_controller.request_approval_sync(request)
if not decision.approved:
    raise PermissionError(f"Approval denied for {name}")
```

### Shell Tool Approval

Shell commands use pattern-based rules:

```yaml
shell_default:
  allowed: false
  approval_required: true

shell_rules:
  - pattern: "git status"
    allowed: true
    approval_required: false
  - pattern: "rm *"
    allowed: false
```

### Approval Configuration Summary

| Tool | Approval Trigger |
|------|------------------|
| `write_file` / `edit_file` | `PathConfig.write_approval: true` |
| `read_file` (for attachments) | `PathConfig.read_approval: true` |
| `shell` | `shell_rules` match or `shell_default.approval_required` |
| `worker_call` | Always (controller mode determines behavior) |
| `worker_create` | Always (controller mode determines behavior) |
| Custom tools | Always (secure by default) |

---

## Dependency Injection

llm-do uses two complementary DI systems:

### PydanticAI's Built-in DI

Passes runtime context into tools:

```python
agent = Agent(model=..., deps_type=WorkerContext)
result = await agent.run(input_data, deps=context)

@agent.tool
async def my_tool(ctx: RunContext[WorkerContext], path: str):
    # Access context via ctx.deps
    ...
```

### Protocol-Based DI

Enables recursive worker calls without circular imports:

```python
# protocols.py - Abstract interfaces
class WorkerDelegator(Protocol):
    async def call_async(self, worker: str, ...) -> Any: ...

# tools.py - Depends on protocols, not runtime
def register_worker_tools(agent, context, delegator: WorkerDelegator, ...):
    @agent.tool(name="worker_call")
    async def worker_call_tool(...):
        return await delegator.call_async(...)

# runtime.py - Provides concrete implementation
class RuntimeDelegator:
    async def call_async(self, worker: str, ...) -> Any:
        # Actual delegation logic
        ...

# Wired together in runtime.py
delegator = RuntimeDelegator(context)
register_worker_tools(agent, context, delegator=delegator, ...)
```

**Why both?**
- **PydanticAI's DI**: Passes data/state into tools
- **Protocol-based DI**: Enables callbacks without coupling

This achieves:
- Clean separation of concerns
- Zero circular dependencies
- Testability (inject mock implementations)
- Recursive worker calls

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
| `tools.py` | ~360 | Tool registration (shell, delegation, custom) |
| `worker_sandbox.py` | ~100 | Sandbox extension with llm-do features |
| `protocols.py` | ~100 | Interface definitions for DI |
| `types.py` | ~200 | Data models (WorkerDefinition, WorkerContext) |
| `registry.py` | ~200 | Worker loading and persistence |
