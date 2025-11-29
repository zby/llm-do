# pydantic-ai-blocking-approval

Synchronous, blocking approval system for PydanticAI agent tools.

## Why This Package?

PydanticAI provides `DeferredToolRequests` for human-in-the-loop approval, but it's designed for **asynchronous, out-of-band** approval flows. This package provides an alternative for **synchronous, blocking** approval - a fundamentally different pattern.

### PydanticAI's Deferred Tools (async/out-of-band)

```
Agent Run → Returns with pending tools → [Time passes] → User approves via API/webhook → Resume agent
```

The deferred pattern is ideal when:
- User isn't present during execution (web apps, background jobs)
- Approval happens out-of-band (email links, admin dashboards, Slack buttons)
- Hours or days may pass between request and approval
- You need to serialize/persist the pending state

### Blocking Approval (this package)

```
Agent Run → Tool needs approval → [Blocks] → User prompted immediately → [Decides] → Execution continues
```

The blocking pattern is ideal when:
- User is present at the terminal (CLI tools, interactive sessions)
- Approval must happen immediately, inline with execution
- The agent run should complete in one continuous session
- You want simple "approve and continue" UX without state management

### Comparison

| Aspect | Deferred (PydanticAI) | Blocking (this package) |
|--------|----------------------|-------------------------|
| **Execution** | Agent run completes, returns pending | Agent run pauses mid-execution |
| **Timing** | Minutes to days between request/approval | Immediate, synchronous |
| **User presence** | Not required during execution | Must be present |
| **State** | Must serialize/persist pending state | No state management needed |
| **Resume** | Explicit resume call with decisions | Automatic after user input |
| **Best for** | Web apps, APIs, async workflows | CLI tools, interactive sessions |

## Installation

```bash
pip install pydantic-ai-blocking-approval
```

## Quick Start

```python
from pydantic_ai import Agent
from pydantic_ai_blocking_approval import (
    ApprovalController,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalToolset,
)

# Create a prompt function for interactive approval
def cli_prompt(request: ApprovalRequest) -> ApprovalDecision:
    print(f"Approve {request.tool_name}? {request.description}")
    response = input("[y/n/s(ession)]: ")
    if response == "s":
        return ApprovalDecision(approved=True, remember="session")
    return ApprovalDecision(approved=response.lower() == "y")

# Wrap your toolset with approval
controller = ApprovalController(mode="interactive", approval_callback=cli_prompt)
approved_toolset = ApprovalToolset(
    inner=my_toolset,
    prompt_fn=controller.approval_callback,
    memory=controller.memory,
)

# Use with PydanticAI agent
agent = Agent(..., toolsets=[approved_toolset])
```

## Approval Modes

The `ApprovalController` supports three modes:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `interactive` | Prompts user via callback | CLI with user present |
| `approve_all` | Auto-approves all requests | Testing, CI |
| `strict` | Auto-denies all requests | Production safety |

```python
# For testing - auto-approve everything
controller = ApprovalController(mode="approve_all")

# For CI/production - reject all approval-required operations
controller = ApprovalController(mode="strict")
```

## Integration Patterns

### Pattern 1: @requires_approval Decorator

Mark individual functions as requiring approval:

```python
from pydantic_ai_blocking_approval import requires_approval

@requires_approval
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email - requires user approval."""
    return f"Email sent to {to}"
```

### Pattern 2: ApprovalAware Toolset

Implement `check_approval()` on your toolset for custom logic:

```python
from pydantic_ai_blocking_approval import ApprovalAware, ApprovalRequest, ApprovalMemory

class MyToolset:
    def check_approval(
        self, tool_name: str, args: dict, memory: ApprovalMemory
    ) -> ApprovalRequest | None:
        if tool_name == "dangerous_operation":
            return ApprovalRequest(
                tool_name=tool_name,
                description=f"Execute {tool_name}",
                payload=args,
            )
        return None  # No approval needed
```

## Session Approval Caching

When users approve with `remember="session"`, subsequent identical requests are auto-approved:

```python
# First call - prompts user
# User selects "approve for session"
decision = ApprovalDecision(approved=True, remember="session")

# Subsequent identical calls - auto-approved from cache
# (same tool_name + payload)
```

The cache key is `(tool_name, payload)`, so tools control matching granularity via their payload design.

## Rich Presentation

Tools can provide enhanced UI hints via `ApprovalPresentation`:

```python
from pydantic_ai_blocking_approval import ApprovalPresentation, ApprovalRequest

request = ApprovalRequest(
    tool_name="write_file",
    description="Write to config.json",
    payload={"path": "config.json"},
    presentation=ApprovalPresentation(
        type="diff",
        content="- old value\n+ new value",
        language="json",
    ),
)
```

Supported presentation types:
- `text` - Plain text
- `diff` - Side-by-side diff
- `file_content` - Syntax-highlighted code
- `command` - Shell command
- `structured` - Tabular/tree data

## API Reference

### Types

- `ApprovalRequest` - Request object when approval is needed
- `ApprovalDecision` - User's decision (approved, note, remember)
- `ApprovalPresentation` - Rich UI hints for display

### Classes

- `ApprovalMemory` - Session cache for "approve for session"
- `ApprovalToolset` - Wrapper that intercepts tool calls
- `ApprovalController` - Mode-based controller

### Protocols

- `ApprovalAware` - Protocol for toolsets with custom `check_approval()`

### Decorators

- `@requires_approval` - Mark functions as needing approval

## License

MIT
