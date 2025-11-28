# Tool Approval System

The tool approval system provides framework-agnostic approval handling for LLM agent tools. It intercepts tool calls, checks if approval is needed, and routes through an approval controller before execution.

## Overview

```
┌─────────────────────────────────────────────────────────┐
│  Approval Layer                                          │
│  - Checks if operation needs approval                    │
│  - Prompts user (interactive) or auto-decides (modes)   │
│  - Session memory for "approve for session"              │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  Tool Layer                                              │
│  - Validates arguments                                   │
│  - Executes the operation                                │
│  - Provides approval metadata via check_approval()       │
└─────────────────────────────────────────────────────────┘
```

## Core Types

All types are defined in `llm_do.tool_approval`:

```python
from llm_do.tool_approval import (
    ApprovalContext,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalController,
    ApprovalToolset,
    requires_approval,
    simple_approval_request,
)
```

### ApprovalContext

Context passed to `check_approval()` methods:

```python
class ApprovalContext(BaseModel):
    tool_name: str              # Name of the tool being called
    args: dict[str, Any]        # Arguments passed to the tool
    metadata: dict[str, Any]    # Framework-specific context (run_id, session_id, etc.)
```

### ApprovalRequest

Returned by tools to request user approval:

```python
class ApprovalRequest(BaseModel):
    tool_name: str                          # What the operator sees
    description: str                        # Human-readable description
    payload: dict[str, Any]                 # Fingerprint for session matching
    presentation: Optional[ApprovalPresentation] = None  # Rich UI hints (future)
    group_id: Optional[str] = None          # For batch approvals (future)
```

### ApprovalDecision

Returned by the approval controller after user interaction:

```python
class ApprovalDecision(BaseModel):
    approved: bool                          # Whether to proceed
    scope: Literal["once", "session"] = "once"  # "session" = don't ask again
    note: Optional[str] = None              # Reason for rejection or comment
```

## ApprovalController

The controller manages approval requests, session memory, and user prompts.

### Modes

```python
from llm_do.tool_approval import ApprovalController

# Interactive mode (default) - prompts user via callback
controller = ApprovalController(
    mode="interactive",
    approval_callback=my_callback,
)

# Auto-approve mode - for tests or non-interactive use
controller = ApprovalController(mode="approve_all")

# Strict mode - rejects all approval-required operations
controller = ApprovalController(mode="strict")
```

### Behavior Matrix

| `check_approval()` returns | Interactive | `approve_all` | `strict` |
|---------------------------|-------------|---------------|----------|
| `None` | Execute | Execute | Execute |
| `ApprovalRequest` | Prompt user | Auto-approve | Auto-deny |
| Raises `PermissionError` | Block | Block | Block |

### Session Approval

When the user selects "approve for session", the controller caches the approval:

```python
# Check if already approved
if controller.is_session_approved(request):
    return ApprovalDecision(approved=True, scope="session")

# Add to session cache
controller.add_session_approval(request)

# Clear all session approvals
controller.clear_session_approvals()
```

Session matching uses `(tool_name, payload)` as the key. Tools control what goes in `payload` to determine matching granularity.

### Methods

```python
# Async - for use in async contexts
decision = await controller.request_approval(request)

# Sync - for use in sync contexts
decision = controller.request_approval_sync(request)

# Get legacy callback for run_worker() compatibility
legacy_callback = controller.get_legacy_callback()
```

## Integration Patterns

### Pattern 1: @requires_approval Decorator

For standalone tool functions:

```python
from llm_do.tool_approval import requires_approval

@requires_approval()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email - requires user approval."""
    return f"Email sent to {to}"

# With custom description
@requires_approval(
    description=lambda args: f"Send email to {args['to']}: {args['subject']}",
)
def send_email(to: str, subject: str, body: str) -> str:
    ...

# Exclude sensitive data from payload
@requires_approval(exclude_keys={"body", "password"})
def send_email(to: str, subject: str, body: str) -> str:
    ...

# Custom payload generator
@requires_approval(
    payload=lambda args: {"recipient": args["to"]},
)
def send_email(to: str, subject: str, body: str) -> str:
    ...
```

The decorator attaches `check_approval()` to the function. The runtime discovers it via `hasattr(func, 'check_approval')`.

### Pattern 2: Toolset-level check_approval()

For class-based toolsets (like `FileSandboxImpl`):

```python
class MyToolset:
    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Single entry point for all tools in this toolset."""
        if ctx.tool_name == "dangerous_operation":
            return ApprovalRequest(
                tool_name=ctx.tool_name,
                description=f"Execute dangerous operation",
                payload=ctx.args,
            )
        return None  # No approval needed for other tools

    def dangerous_operation(self, param: str) -> str:
        ...

    def safe_operation(self, param: str) -> str:
        ...
```

### Pattern 3: ApprovalToolset Wrapper

Wraps any PydanticAI toolset with approval checking:

```python
from llm_do.tool_approval import ApprovalToolset, ApprovalController
from pydantic_ai import Agent

# Create inner toolset
sandbox = FileSandboxImpl(config)

# Wrap with approval
controller = ApprovalController(mode="interactive", approval_callback=my_callback)
approval_sandbox = ApprovalToolset(sandbox, controller)

# Use with agent
agent = Agent(..., toolsets=[approval_sandbox])
```

The `ApprovalToolset`:
1. Checks if inner toolset has `check_approval()`
2. Calls it before each tool execution
3. Routes `ApprovalRequest` through the controller
4. Raises `PermissionError` if denied

## Configuration

### Sandbox Write Approval

Require approval for file writes via `PathConfig.write_approval`:

```yaml
sandbox:
  paths:
    output:
      root: ./output
      mode: rw
      write_approval: true  # Writes require approval
```

### Sandbox Read Approval

Require approval for sharing files as attachments via `PathConfig.read_approval`:

```yaml
sandbox:
  paths:
    documents:
      root: ./docs
      mode: ro
      read_approval: true  # Reading for attachments requires approval
```

### Custom Tools

List allowed custom tools via `custom_tools`:

```yaml
custom_tools:
  - calculate_fibonacci
  - send_notification
```

Tools must be defined in `tools.py` and use `@requires_approval` if they need approval.

### Shell Commands

Shell approval is controlled by `shell_default` and `shell_rules`:

```yaml
shell_default:
  allowed: false
  approval_required: true

shell_rules:
  - pattern: "git status"
    allowed: true
    approval_required: false
  - pattern: "git commit"
    allowed: true
    approval_required: true
```

## Factory Function

For simple approval requests:

```python
from llm_do.tool_approval import simple_approval_request

request = simple_approval_request(
    tool_name="my_tool",
    args={"path": "/data/file.txt", "content": "..."},
    description="Write to file",           # Optional, auto-generated if None
    exclude_keys={"content"},              # Optional, exclude from payload
)
```

## Usage in Tools

### Reading Context

```python
from pydantic_ai import RunContext
from llm_do import WorkerContext
from llm_do.tool_approval import ApprovalRequest

@agent.tool
def my_tool(ctx: RunContext[WorkerContext], path: str) -> str:
    # Request approval via the controller
    request = ApprovalRequest(
        tool_name="my_tool",
        description=f"Process {path}",
        payload={"path": path},
    )
    decision = ctx.deps.approval_controller.request_approval_sync(request)
    if not decision.approved:
        raise PermissionError(f"Approval denied: {decision.note}")

    return do_work(path)
```

### Built-in Tool Approval

These tools always go through the approval controller:

| Tool | Approval Trigger |
|------|------------------|
| `write_file` | `PathConfig.write_approval: true` |
| `read_file` (for attachments) | `PathConfig.read_approval: true` |
| `shell` | `shell_rules` match or `shell_default.approval_required` |
| `worker_call` | Always (controller mode determines behavior) |
| `worker_create` | Always (controller mode determines behavior) |

## Guidelines for Tool Authors

### Payload Design

The `payload` field determines session approval matching:

```python
# Fine-grained: each file separately approved
payload={"path": "/data/report.txt"}

# Coarse-grained: all writes to sandbox approved together
payload={"sandbox": "data"}

# Pattern-based: all git status commands approved
payload={"command_pattern": "git status"}
```

### Best Practices

| Scenario | Payload Strategy |
|----------|-----------------|
| File operations | Include path, exclude content |
| Shell commands | Include command/pattern, exclude output |
| API calls | Include endpoint + method, exclude body |
| Sensitive data | Use `exclude_keys` to omit secrets |

### Avoid Volatile Data

Don't include data that changes between calls:

```python
# Bad: content changes, session approval never matches
payload={"path": path, "content": content}

# Good: just the path, content can vary
payload={"path": path}
```

## Module Reference

```
llm_do/tool_approval.py
├── ApprovalPresentation    # Rich UI hints (future)
├── ApprovalContext         # Context for check_approval()
├── ApprovalRequest         # Returned to request approval
├── ApprovalDecision        # Returned after user interaction
├── ApprovalAware           # Protocol for approval-aware tools
├── ApprovalController      # Manages approvals and session memory
├── ApprovalToolset         # PydanticAI toolset wrapper
├── requires_approval()     # Decorator for tool functions
└── simple_approval_request()  # Factory for basic requests
```
