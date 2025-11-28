# Tool Approval Redesign

**Status:** Proposed
**Date:** 2024-11-28

## Summary

Adopt PydanticAI's deferred tool approval pattern (`DeferredToolRequests`/`DeferredToolResults`) instead of our custom blocking wrapper. This aligns with PydanticAI's official approach while providing a clean synchronous API for CLI use cases.

## Background

### PydanticAI's Deferred Pattern

PydanticAI v1.0+ provides native human-in-the-loop approval via:
- `ApprovalRequiredToolset` - wraps toolsets to require approval
- `DeferredToolRequests` - returned when tools need approval
- `DeferredToolResults` - passed back with approval decisions

```python
# Agent stops and returns DeferredToolRequests
result = agent.run_sync(prompt)
if isinstance(result.output, DeferredToolRequests):
    # Collect approvals (can be interactive CLI, web UI, etc.)
    approvals = collect_approvals_sync(result.output, ui=cli_ui)
    # Resume with approval decisions
    result = agent.run_sync(
        message_history=result.all_messages(),
        deferred_tool_results=approvals,
    )
```

### Why Adopt This Pattern?

| Aspect | Old (Blocking Wrapper) | New (Deferred) |
|--------|----------------------|----------------|
| PydanticAI alignment | Diverges | Native pattern |
| Batching approvals | One at a time | All pending at once |
| Code complexity | Custom wrapper (~200 lines) | Thin adapter (~100 lines) |
| UI flexibility | Tied to wrapper | Clean `ApprovalUI` protocol |
| Testability | Hard to test | Pure functions |

**Decision:** Adopt PydanticAI's deferred pattern with a synchronous collection API.

## Current Problems

### 1. Custom Wrapper Diverges from PydanticAI

Our `ApprovalToolset` intercepts `call_tool()` and blocks inside the agent run. This fights PydanticAI's design rather than embracing it.

### 2. Duplicate Type Definitions

Types duplicated in `tool_approval.py` and `filesystem_sandbox.py`.

### 3. Complex Integration

Two different patterns: `@requires_approval` decorator vs `check_approval()` method.

## Proposed Design

### Core Types

```python
# llm_do/tool_approval.py
from dataclasses import dataclass, field
from typing import Any, Mapping, Literal, Protocol

from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolApproved, ToolDenied

ApprovalMode = Literal["interactive", "auto_approve", "auto_deny"]


@dataclass
class ApprovalRequest:
    """
    A single tool call that needs human approval.
    Presentation-friendly view of a ToolCallPart from DeferredToolRequests.
    """
    tool_call_id: str
    tool_name: str
    args: Mapping[str, Any]
    metadata: Mapping[str, Any] | None = None
    summary: str | None = None  # e.g. "delete file .env"


@dataclass
class ApprovalDecision:
    """Human (or policy) decision about a single tool call."""
    approved: bool
    note: str | None = None
    override_args: Mapping[str, Any] | None = None
    remember: Literal["none", "session", "always"] = "none"
```

### UI Protocol

```python
class ApprovalUI(Protocol):
    """
    Sync UI hook for interactive workflows.
    Implementations: CLI prompts, TUI, web handler, etc.
    """
    def choose(self, request: ApprovalRequest, *, mode: ApprovalMode) -> ApprovalDecision:
        ...
```

### Session Memory

```python
@dataclass
class ApprovalMemory:
    """Cache to avoid re-asking for identical tool calls."""
    decisions: dict[tuple[str, str], ApprovalDecision] = field(default_factory=dict)

    def lookup(self, req: ApprovalRequest) -> ApprovalDecision | None:
        key = (req.tool_name, self._stable_arg_key(req.args))
        return self.decisions.get(key)

    def store(self, req: ApprovalRequest, decision: ApprovalDecision) -> None:
        if decision.remember == "none":
            return
        key = (req.tool_name, self._stable_arg_key(req.args))
        self.decisions[key] = decision

    @staticmethod
    def _stable_arg_key(args: Mapping[str, Any]) -> str:
        import json
        return json.dumps(args, sort_keys=True, default=str)
```

### Pure Transformation

```python
def build_approval_requests(requests: DeferredToolRequests) -> list[ApprovalRequest]:
    """
    Transform PydanticAI's DeferredToolRequests into our ApprovalRequest objects.
    """
    out: list[ApprovalRequest] = []
    for call in requests.approvals:
        metadata = (
            requests.metadata.get(call.tool_call_id)
            if requests.metadata else None
        )
        summary = None
        if isinstance(metadata, Mapping):
            summary = metadata.get("summary") or metadata.get("reason") or metadata.get("path")

        out.append(ApprovalRequest(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            args=call.args,
            metadata=metadata,
            summary=summary,
        ))
    return out
```

### Main API

```python
def collect_approvals_sync(
    requests: DeferredToolRequests,
    *,
    ui: ApprovalUI,
    mode: ApprovalMode = "interactive",
    memory: ApprovalMemory | None = None,
) -> DeferredToolResults:
    """
    Synchronously collect approvals for all tool calls in `requests`.

    This is the main API for CLI/UI code.
    """
    results = DeferredToolResults()
    memory = memory or ApprovalMemory()

    for req in build_approval_requests(requests):
        # 1. Check cached decision
        cached = memory.lookup(req)
        if cached is not None:
            decision = cached
        # 2. Policy shortcuts
        elif mode == "auto_approve":
            decision = ApprovalDecision(approved=True)
        elif mode == "auto_deny":
            decision = ApprovalDecision(approved=False)
        # 3. Human-in-the-loop
        else:
            decision = ui.choose(req, mode=mode)

        # Store if user asked to remember
        if decision.remember != "none":
            memory.store(req, decision)

        # Convert to PydanticAI types
        if decision.approved:
            if decision.override_args:
                results.approvals[req.tool_call_id] = ToolApproved(
                    override_args=dict(decision.override_args)
                )
            else:
                results.approvals[req.tool_call_id] = True
        else:
            if decision.note:
                results.approvals[req.tool_call_id] = ToolDenied(decision.note)
            else:
                results.approvals[req.tool_call_id] = False

    return results
```

## How Tools Request Approval

### Option 1: ApprovalRequiredToolset (for toolsets)

```python
from pydantic_ai.toolsets import ApprovalRequiredToolset

# Wrap FileSandbox to require approval for writes
def needs_approval(ctx, tool_def, args) -> bool:
    if tool_def.name == "write_file":
        return True
    if tool_def.name == "read_file":
        # Check if path config requires read approval
        return sandbox.needs_read_approval(args.get("path"))
    return False

approved_sandbox = sandbox.approval_required(needs_approval)
agent = Agent(..., toolsets=[approved_sandbox])
```

### Option 2: Metadata for Rich Context

Tools can provide metadata for better approval UX:

```python
from pydantic_ai.exceptions import ApprovalRequired

@agent.tool
def write_file(ctx: RunContext, path: str, content: str) -> str:
    if not ctx.tool_call_approved:
        raise ApprovalRequired(
            metadata={"summary": f"Write {len(content)} chars to {path}", "path": path}
        )
    return do_write(path, content)
```

## Usage Pattern

### Simple Case

```python
from llm_do.tool_approval import collect_approvals_sync, ApprovalMemory

memory = ApprovalMemory()

result = agent.run_sync(prompt, output_type=[OutputT, DeferredToolRequests])

while isinstance(result.output, DeferredToolRequests):
    approvals = collect_approvals_sync(
        result.output,
        ui=cli_ui,
        mode="interactive",
        memory=memory,
    )
    result = agent.run_sync(
        message_history=result.all_messages(),
        deferred_tool_results=approvals,
    )

return result.output
```

### Helper Function

```python
def run_with_approval(
    agent: Agent,
    prompt: str,
    *,
    ui: ApprovalUI,
    mode: ApprovalMode = "interactive",
    memory: ApprovalMemory | None = None,
) -> Any:
    """Run agent with automatic approval handling."""
    memory = memory or ApprovalMemory()
    history = None
    deferred = None

    while True:
        result = agent.run_sync(
            prompt,
            message_history=history,
            deferred_tool_results=deferred,
            output_type=[Any, DeferredToolRequests],
        )

        if not isinstance(result.output, DeferredToolRequests):
            return result.output

        deferred = collect_approvals_sync(result.output, ui=ui, mode=mode, memory=memory)
        history = result.all_messages()
```

## File Structure After Redesign

```
llm_do/
├── tool_approval.py         # REWRITTEN: Deferred-based approval
│   ├── ApprovalRequest      # Our presentation type
│   ├── ApprovalDecision     # Our decision type
│   ├── ApprovalUI           # Protocol for UI implementations
│   ├── ApprovalMemory       # Session caching
│   ├── build_approval_requests()
│   └── collect_approvals_sync()
│
├── cli.py                   # CLI implementation of ApprovalUI
├── filesystem_sandbox.py    # SIMPLIFIED: Remove approval types, use ApprovalRequiredToolset
├── execution.py             # Use run_with_approval() helper
└── ...
```

## Migration Steps

### Phase 1: Add New Module (Non-breaking)

1. Create new `tool_approval.py` with deferred-based types
2. Keep old code working alongside
3. Add `run_with_approval()` helper

### Phase 2: Update FileSandbox

1. Remove inline approval types from `filesystem_sandbox.py`
2. Use `ApprovalRequiredToolset` wrapper instead of custom `check_approval()`
3. Add metadata to approval requests for better UX

### Phase 3: Update Runtime

1. Update `execution.py` to use `run_with_approval()`
2. Update CLI to implement `ApprovalUI` protocol
3. Remove old `ApprovalToolset` wrapper

### Phase 4: Cleanup

1. Remove old approval controller code
2. Remove `@requires_approval` decorator (use PydanticAI's native approach)
3. Update tests

## What Changes

| Before | After |
|--------|-------|
| `ApprovalToolset` wrapper | `ApprovalRequiredToolset` (PydanticAI native) |
| `check_approval()` method | `approval_required(func)` on toolset |
| `ApprovalController` class | `collect_approvals_sync()` function |
| Blocking inside `call_tool()` | Stop/resume with message history |
| One approval at a time | Batch all pending approvals |

## What We Keep

- **Session caching** via `ApprovalMemory` (remember="session")
- **Approval modes** - interactive/auto_approve/auto_deny
- **Rich presentation** - metadata passed through for summaries, diffs
- **Synchronous CLI UX** - `collect_approvals_sync()` blocks for user input

## What We Remove

- **Custom `ApprovalToolset` wrapper** - ~200 lines
- **Custom `ApprovalController` class** - ~100 lines
- **Duplicate types in filesystem_sandbox.py** - ~170 lines
- **`@requires_approval` decorator** - use PydanticAI's native approach
- **`ApprovalAware` protocol** - not needed with deferred pattern

## Estimated Impact

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| tool_approval.py | 524 lines | ~150 lines | -71% |
| filesystem_sandbox.py | 911 lines | ~600 lines | -34% |
| Custom approval code | ~700 lines | ~150 lines | -79% |
| PydanticAI alignment | Diverges | Native | ✓ |

## Open Questions

1. **Upgrade PydanticAI version?** Current requirement is `>=0.0.13`. Need `>=1.0.0` for `DeferredToolRequests`.

2. **Async version needed?** Should we also provide `collect_approvals_async()` for async runtimes?

3. **Nested workers** - When worker A calls worker B, how do approvals bubble up? Need to test this flow.

## References

- PydanticAI Deferred Tools: https://ai.pydantic.dev/deferred-tools/
- PydanticAI Toolsets: https://ai.pydantic.dev/toolsets/
- Current implementation: `llm_do/tool_approval.py`
- Current sandbox: `llm_do/filesystem_sandbox.py`
