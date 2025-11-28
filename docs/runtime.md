# Runtime API

The runtime module provides the core worker execution API.

## Entry Points

### run_worker / run_worker_async

Primary entry points for executing workers.

```python
from llm_do import run_worker, run_worker_async

# Sync version
result = run_worker(
    registry=registry,
    worker="my-worker",
    input_data={"task": "..."},
    attachments=None,                 # Optional files to expose
    cli_model="openai:gpt-4",         # Fallback model
    approval_controller=controller,   # For tool approvals
    message_callback=on_message,      # For streaming events
)

# Async version (recommended for nested worker calls)
result = await run_worker_async(
    registry=registry,
    worker="my-worker",
    input_data={"task": "..."},
    # ... same parameters
)
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `registry` | `WorkerRegistry` | Source for worker definitions |
| `worker` | `str` | Name of the worker to run |
| `input_data` | `Any` | Input payload (string or dict) |
| `attachments` | `Sequence[AttachmentInput]` | Optional files to expose |
| `cli_model` | `ModelLike` | Fallback model if worker has none |
| `approval_controller` | `ApprovalController` | Controller for tool approvals |
| `message_callback` | `MessageCallback` | Callback for streaming events |

**Returns:** `WorkerRunResult` with `output` and `messages`.

**Implementation Note:** Both functions share preparation logic through internal helpers (`_prepare_worker_context`, `_handle_result`) to avoid duplication while maintaining separate sync/async execution paths.

---

### call_worker / call_worker_async

Delegate to another worker (used internally by `worker_call` tool).

```python
result = await call_worker_async(
    registry=registry,
    worker="target-worker",
    input_data=payload,
    caller_context=context,    # Required: parent worker's context
    attachments=files,
)
```

**Enforces:**
- `allow_workers` allowlist from the caller's definition
- Attachment approval via `sandbox.read` with full metadata (path, size, target worker)
- Attachment policy limits (max count, total size, allowed suffixes)

**Note:** When delegating with attachments, each attachment triggers a `sandbox.read` approval check before being passed to the child worker. This ensures the user is aware of what files are being shared between workers.

---

### create_worker

Create and persist a new worker definition.

```python
from llm_do import create_worker, WorkerSpec, WorkerCreationDefaults

spec = WorkerSpec(
    name="new-worker",
    instructions="You are a helpful assistant.",
    description="A simple worker",
)

definition = create_worker(
    registry=registry,
    spec=spec,
    defaults=WorkerCreationDefaults(default_model="openai:gpt-4"),
    force=False,  # Set True to overwrite existing
)
```

Workers are saved to `workers/generated/{name}.worker`.

---

## Protocol Implementations

Used internally for dependency injection. See [dependency_injection.md](dependency_injection.md).

### RuntimeDelegator

Implements `WorkerDelegator` protocol. Handles worker delegation with approval enforcement.

```python
class RuntimeDelegator:
    def __init__(self, context: WorkerContext): ...
    async def call_async(self, worker: str, input_data: Any, attachments: list[str]) -> Any: ...
    def call_sync(self, worker: str, input_data: Any, attachments: list[str]) -> Any: ...
```

**Attachment approval enforcement:** When attachments are provided, `RuntimeDelegator` validates them through `AttachmentValidator`, then checks `sandbox.read` approval for each attachment before passing them to the child worker.

### RuntimeCreator

Implements `WorkerCreator` protocol. Handles worker creation with approval enforcement.

```python
class RuntimeCreator:
    def __init__(self, context: WorkerContext): ...
    def create(self, name: str, instructions: str, ...) -> dict: ...
```

---

## WorkerContext

Runtime context passed to worker execution and available to tools via PydanticAI's dependency injection.

```python
@dataclass
class WorkerContext:
    registry: WorkerRegistry
    worker: WorkerDefinition
    attachment_validator: AttachmentValidator
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController  # Unified approval for all tools
    sandbox: Optional[AbstractToolset]       # FileSandbox toolset wrapped with ApprovalToolset
    attachments: List[AttachmentPayload]
    message_callback: Optional[MessageCallback]
    custom_tools_path: Optional[Path]

    def validate_attachments(
        self, attachment_specs: Sequence[AttachmentInput]
    ) -> tuple[List[Path], List[Dict[str, Any]]]:
        """Resolve attachment specs to sandboxed files and enforce policy limits."""
```

**Key components:**

- **`attachment_validator`**: Validates and resolves attachments for worker delegation
- **`approval_controller`**: Unified approval controller for all tools (from `tool_approval.py`)
- **`sandbox`**: The FileSandbox toolset wrapped with ApprovalToolset for approval checking
- **`attachments`**: Files passed to this worker from parent (if delegated)
- **`custom_tools_path`**: Path to `tools.py` if worker has custom tools

Tools access context via `RunContext[WorkerContext]`:

```python
from pydantic_ai import RunContext
from llm_do import WorkerContext
from llm_do.tool_approval import ApprovalRequest

@agent.tool
def my_tool(ctx: RunContext[WorkerContext], arg: str) -> str:
    # Access worker definition
    worker_name = ctx.deps.worker.name

    # Request approval via the unified controller
    request = ApprovalRequest(
        tool_name="my_tool",
        description=f"Execute my_tool with arg={arg}",
        payload={"arg": arg},
    )
    decision = ctx.deps.approval_controller.request_approval_sync(request)
    if not decision.approved:
        raise PermissionError(f"Approval denied: {decision.note}")

    return perform_operation(arg)
```

**Note:** File operations are handled through the `Sandbox` toolset registered automatically. Tools like `read_file`, `write_file`, and `list_files` are available based on the worker's sandbox configuration.

---

## Tool Approval Architecture

llm-do has two approval systems that work together:

1. **Tool Rules (`approval.py`)**: Legacy system for `worker.call`, `worker.create`, `sandbox.read`
2. **Tool Approval (`tool_approval.py`)**: New framework-agnostic system for filesystem tools

> **Design document**: See [docs/design/tool_approval_architecture.md](design/tool_approval_architecture.md) for the full architecture.

### New Tool Approval System

The new system is framework-agnostic and based on tools declaring their approval needs:

```python
from llm_do.tool_approval import (
    ApprovalContext,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalController,
    ApprovalToolset,
    requires_approval,
)
```

#### Core Types

| Type | Purpose |
|------|---------|
| `ApprovalContext` | Framework-agnostic context passed to `check_approval()` |
| `ApprovalRequest` | Returned by tools when approval is needed |
| `ApprovalDecision` | Result from the approval controller |
| `ApprovalController` | Manages session memory, modes (interactive/approve_all/strict) |
| `ApprovalToolset` | PydanticAI wrapper that intercepts tool calls for approval |

#### Pattern 1: Decorated Functions

For simple standalone tools:

```python
from llm_do.tool_approval import requires_approval

@requires_approval()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email - always requires approval."""
    return f"Email sent to {to}"

@requires_approval(
    description=lambda args: f"Send email to {args['to']}",
    exclude_keys={"body"},  # Don't include body in approval payload
)
def send_email_v2(to: str, subject: str, body: str) -> str:
    ...
```

#### Pattern 2: Toolset-Level Checker

For class-based toolsets (like `FileSandboxImpl`):

```python
class FileSandboxImpl(AbstractToolset):
    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Single entry point for all tools in this toolset."""
        if ctx.tool_name == "write_file":
            return self._check_write_approval(ctx)
        elif ctx.tool_name == "read_file":
            return self._check_read_approval(ctx)
        return None  # No approval needed for list_files
```

#### ApprovalToolset Wrapper

Wraps any PydanticAI toolset with approval checking:

```python
from llm_do.tool_approval import ApprovalToolset, ApprovalController

sandbox = FileSandboxImpl(config)
controller = ApprovalController(mode="interactive", approval_callback=...)
approval_sandbox = ApprovalToolset(sandbox, controller)

# approval_sandbox checks sandbox.check_approval() before each tool call
agent = Agent(..., toolsets=[approval_sandbox])
```

#### Controller Modes

| Mode | Behavior |
|------|----------|
| `interactive` | Prompts user via callback |
| `approve_all` | Auto-approves all `ApprovalRequest`s |
| `strict` | Auto-denies all `ApprovalRequest`s |

```python
# Auto-approve mode (for tests)
controller = ApprovalController(mode="approve_all")

# Strict mode (for CI/production)
controller = ApprovalController(mode="strict")
```

---

## Approval Controllers

```python
from llm_do import ApprovalController, ApprovalDecision
from llm_do.tool_approval import ApprovalRequest

# Auto-approve everything (for tests)
result = run_worker(..., approval_controller=ApprovalController(mode="approve_all"))

# Reject all approval-required tools (strict mode)
result = run_worker(..., approval_controller=ApprovalController(mode="strict"))

# Custom interactive approval
def my_callback(request: ApprovalRequest) -> ApprovalDecision:
    # Show prompt to user, get decision
    print(f"Approve {request.tool_name}? {request.description}")
    return ApprovalDecision(
        approved=True,
        scope="session",  # Don't ask again for same operation
        note="User approved via CLI",
    )

controller = ApprovalController(mode="interactive", approval_callback=my_callback)
result = run_worker(..., approval_controller=controller)
```

**Built-in modes:**
- `mode="approve_all"`: Auto-approves all requests (testing, non-interactive)
- `mode="strict"`: Rejects all approval-required tools (production, CI)
- `mode="interactive"`: Uses custom callback for user prompts

---

## Module Structure

The runtime is organized into focused modules with clear responsibilities:

```
llm_do/
├── runtime.py           # Worker execution and delegation
│                        # - run_worker / run_worker_async
│                        # - call_worker / call_worker_async
│                        # - create_worker
│                        # - RuntimeDelegator / RuntimeCreator
│                        # - Internal helpers: _prepare_worker_context, _handle_result
│
├── execution.py         # Agent execution strategies
│                        # - default_agent_runner (sync wrapper)
│                        # - default_agent_runner_async (PydanticAI integration)
│                        # - prepare_agent_execution (context prep)
│                        # - ApprovalToolset wrapping for sandbox
│
├── types.py             # Type definitions and data models
│                        # - WorkerDefinition, WorkerSpec, WorkerContext
│                        # - AgentRunner, MessageCallback
│
├── tool_approval.py     # Framework-agnostic approval system
│                        # - ApprovalController (modes: interactive, approve_all, strict)
│                        # - ApprovalContext, ApprovalRequest, ApprovalDecision
│                        # - ApprovalController (session memory, modes)
│                        # - ApprovalToolset (PydanticAI wrapper)
│                        # - @requires_approval decorator
│                        # - simple_approval_request factory
│
├── tools.py             # Tool registration
│                        # - register_worker_tools
│                        # - File tools (read_file, write_file, list_files)
│                        # - Shell tool (shell)
│                        # - Delegation tools (worker_call, worker_create)
│
├── protocols.py         # Dependency injection protocols
│                        # - WorkerDelegator, WorkerCreator, FileSandbox
│
├── worker_sandbox.py    # Sandbox for worker execution
│                        # - Sandbox (unified sandbox implementation)
│                        # - SandboxConfig (paths configuration)
│                        # - AttachmentValidator (attachment validation)
│
└── filesystem_sandbox.py # Reusable filesystem sandbox
                         # - FileSandboxImpl (AbstractToolset + ApprovalAware)
                         # - PathConfig (path-level configuration with approval flags)
                         # - check_approval() for filesystem operations
```

**Architecture highlights:**

- **Separation of concerns**: Runtime orchestration separated from agent execution
- **Dependency injection**: Protocols enable testability and flexibility
- **Shared helpers**: `_prepare_worker_context` eliminates ~110 lines of duplication
- **Async-first**: `run_worker` wraps async implementation for backward compatibility
- **Framework-agnostic approval**: `tool_approval.py` types can be extracted for use with any LLM framework
