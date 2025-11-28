# Tool Approval System

The tool approval system provides framework-agnostic approval handling for LLM agent tools. It intercepts tool calls, checks if approval is needed, and prompts the user before execution.

## Overview

```
┌─────────────────────────────────────────────────────────┐
│  Approval Layer (ApprovalToolset)                        │
│  - Checks if operation needs approval                    │
│  - Prompts user (via prompt_fn) or auto-decides (modes) │
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
    ApprovalRequest,
    ApprovalDecision,
    ApprovalMemory,
    ApprovalController,
    ApprovalToolset,
    requires_approval,
)
```

### ApprovalRequest

Returned by `check_approval()` to request user approval:

```python
class ApprovalRequest(BaseModel):
    tool_name: str                          # What the operator sees
    description: str                        # Human-readable description
    payload: dict[str, Any]                 # Fingerprint for session matching
    presentation: Optional[ApprovalPresentation] = None  # Rich UI hints
```

### ApprovalDecision

Returned after user interaction:

```python
class ApprovalDecision(BaseModel):
    approved: bool                          # Whether to proceed
    note: Optional[str] = None              # Reason for rejection or comment
    remember: Literal["none", "session"] = "none"  # "session" = don't ask again
```

### ApprovalMemory

Session cache to avoid re-prompting for identical calls:

```python
class ApprovalMemory:
    def lookup(self, tool_name: str, args: dict) -> Optional[ApprovalDecision]:
        """Look up a previous approval decision."""
        ...

    def store(self, tool_name: str, args: dict, decision: ApprovalDecision) -> None:
        """Store an approval decision for session reuse."""
        ...

    def clear(self) -> None:
        """Clear all session approvals."""
        ...
```

Session matching uses `(tool_name, payload)` as the key. Tools control what goes in `payload` to determine matching granularity.

## ApprovalController

The controller manages approval mode and provides prompt functions.

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

### Methods

```python
# Check if already approved for session
controller.is_session_approved(request)

# Clear all session approvals
controller.clear_session_approvals()

# Get approval callback for ApprovalToolset
controller.approval_callback  # Returns Callable[[ApprovalRequest], ApprovalDecision]

# Get memory for ApprovalToolset
controller.memory  # Returns ApprovalMemory
```

## Integration Patterns

### Pattern 1: @requires_approval Decorator

For standalone tool functions, use the marker decorator:

```python
from llm_do.tool_approval import requires_approval

@requires_approval
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email - requires user approval."""
    return f"Email sent to {to}"

@requires_approval
def delete_file(path: str) -> str:
    """Delete a file - requires user approval."""
    ...
```

The decorator marks the function as requiring approval. `ApprovalToolset` detects this marker and creates a basic `ApprovalRequest` from the function name and args.

### Pattern 2: Toolset-level check_approval()

For class-based toolsets (like `FileSandboxImpl`):

```python
class MyToolset:
    def check_approval(
        self, tool_name: str, args: dict, memory: ApprovalMemory
    ) -> Optional[ApprovalRequest]:
        """Single entry point for all tools in this toolset.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments
            memory: Session approval cache - can check for pattern matches

        Returns:
            None - No approval needed, proceed with execution
            ApprovalRequest - Approval required before execution

        Raises:
            PermissionError - Operation is blocked entirely
        """
        if tool_name == "dangerous_operation":
            return ApprovalRequest(
                tool_name=tool_name,
                description=f"Execute dangerous operation",
                payload=args,
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
from llm_do.tool_approval import ApprovalToolset, ApprovalController, ApprovalMemory
from pydantic_ai import Agent

# Create inner toolset
sandbox = FileSandboxImpl(config)

# Option A: Use ApprovalController for mode-based approval
controller = ApprovalController(mode="interactive", approval_callback=my_callback)
approval_sandbox = ApprovalToolset(
    inner=sandbox,
    prompt_fn=controller.approval_callback,
    memory=controller.memory,
)

# Option B: Use prompt function directly
memory = ApprovalMemory()
approval_sandbox = ApprovalToolset(
    inner=sandbox,
    prompt_fn=cli_prompt,
    memory=memory,
)

# Use with agent
agent = Agent(..., toolsets=[approval_sandbox])
```

The `ApprovalToolset`:
1. Checks if inner toolset has `check_approval(tool_name, args, memory)`
2. Calls it before each tool execution
3. Prompts via `prompt_fn` if approval required
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

## Usage in Tools

Tools typically don't need to handle approvals directly - they implement `check_approval()` and let `ApprovalToolset` handle the prompting. However, for manual approval handling:

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
├── ApprovalPresentation    # Rich UI hints (diffs, syntax highlighting)
├── ApprovalRequest         # Returned by check_approval()
├── ApprovalDecision        # User's decision
├── ApprovalMemory          # Session cache for "approve for session"
├── ApprovalAware           # Protocol for approval-aware toolsets
├── ApprovalController      # Mode-based prompt function provider
├── ApprovalToolset         # PydanticAI toolset wrapper (uses __getattr__ delegation)
└── requires_approval       # Marker decorator for functions
```
