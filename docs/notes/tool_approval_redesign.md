# Tool Approval Redesign

**Status:** Proposed
**Date:** 2024-11-28

## Summary

Simplify the tool approval architecture while keeping the synchronous blocking pattern that works well for CLI use cases. Remove duplication, reduce boilerplate, and keep `check_approval()` synchronous (approval prompting/blocking happens in the controller, not the check).

## Background

### Why Not PydanticAI's Native `ApprovalRequired`?

PydanticAI v1.0+ provides `ApprovalRequired` exception and `ApprovalRequiredToolset` for human-in-the-loop approval. However, these use a **deferred pattern**:

```python
# PydanticAI deferred pattern - agent STOPS and returns control
result = await agent.run(prompt)
if isinstance(result.output, DeferredToolRequests):
    # Agent has stopped - approval could happen hours later
    # Must start NEW agent run with approval results
    result = await agent.run(prompt, message_history=..., deferred_tool_results=...)
```

llm-do uses a **synchronous blocking pattern** that's better for CLI:

```python
# llm-do synchronous pattern - agent BLOCKS inside tool execution
async def call_tool(self, name, args, ctx, tool):
    decision = await controller.request_approval(...)  # BLOCKS here
    if not decision.approved:
        raise PermissionError("Denied")
    return await self._inner.call_tool(...)  # Continue same run
```

| Aspect | Deferred (PydanticAI) | Synchronous (llm-do) |
|--------|----------------------|---------------------|
| Agent state | Serialized between runs | Continuous single run |
| Message history | Must pass explicitly | Automatic |
| Approval timing | Hours/days later | Immediate (CLI) |
| Session caching | Not built-in | Natural fit |
| Use case | Web apps, async | CLI, interactive |

**Decision:** Keep synchronous pattern for CLI use case.

## Current Problems

### 1. Duplicate Type Definitions

`filesystem_sandbox.py` has inline copies of approval types for "standalone" use:

```
llm_do/tool_approval.py:
  - ApprovalContext
  - ApprovalRequest
  - ApprovalDecision
  - ApprovalController
  - ApprovalToolset

llm_do/filesystem_sandbox.py:
  - ApprovalContext      # DUPLICATE
  - ApprovalRequest      # DUPLICATE
  - ApprovalDecision     # DUPLICATE
  - ApprovalController   # DUPLICATE
  - ApprovalToolsetWrapper  # DUPLICATE
```

### 2. Wrapper Boilerplate

`ApprovalToolset` manually delegates every `AbstractToolset` method:

```python
class ApprovalToolset(AbstractToolset):
    @property
    def id(self): return getattr(self._inner, "id", None)
    @property
    def label(self): return getattr(self._inner, "label", ...)
    @property
    def tool_name_conflict_hint(self): return getattr(...)
    async def __aenter__(self): ...
    async def __aexit__(self): ...
    async def get_tools(self): return await self._inner.get_tools(ctx)
    # ... ~50 lines of delegation
```

### 3. Two Check Patterns

Function tools use `@requires_approval` decorator, class toolsets use `check_approval()` method. Different signatures, different integration paths.

### 4. ApprovalAware Protocol is Sync-Only

```python
class ApprovalAware(Protocol):
    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        ...  # Sync only - can't do async presentation generation
```

## Proposed Changes

### 1. Single Source for Approval Types

Create `llm_do/approval.py` with all approval types:

```python
# llm_do/approval.py - Single source of truth
from pydantic import BaseModel

class ApprovalContext(BaseModel):
    tool_name: str
    args: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

class ApprovalRequest(BaseModel):
    tool_name: str
    description: str
    payload: dict[str, Any]

class ApprovalDecision(BaseModel):
    approved: bool
    scope: Literal["once", "session"] = "once"
    note: Optional[str] = None
```

Update imports everywhere:
```python
# Before
from llm_do.tool_approval import ApprovalContext, ApprovalRequest

# After
from llm_do.approval import ApprovalContext, ApprovalRequest
```

### 2. Simplified Wrapper with `__getattr__`

Replace manual delegation with automatic forwarding:

```python
class ApprovalToolset(AbstractToolset):
    """Wraps a toolset with synchronous approval checking."""

    def __init__(self, inner: AbstractToolset, controller: ApprovalController):
        self._inner = inner
        self._controller = controller

    def __getattr__(self, name: str) -> Any:
        """Forward unknown attributes to inner toolset."""
        return getattr(self._inner, name)

    async def call_tool(self, name: str, args: dict, ctx: Any, tool: Any) -> Any:
        """Intercept tool calls for approval checking."""
        request = self._get_approval_request(name, args)
        if request:
            decision = await self._controller.request_approval(request)
            if not decision.approved:
                raise PermissionError(f"Denied: {name}")
        return await self._inner.call_tool(name, args, ctx, tool)

    def _get_approval_request(self, name: str, args: dict) -> Optional[ApprovalRequest]:
        """Get approval request from inner toolset if it supports approval."""
        if hasattr(self._inner, "check_approval"):
            ctx = ApprovalContext(tool_name=name, args=args)
            return self._inner.check_approval(ctx)
        return None
```

**Reduction:** ~50 lines → ~20 lines

### 3. Unified Check Function Signature

Adopt PydanticAI-compatible signature for approval checks:

```python
# New signature (matches PydanticAI's ApprovalRequiredToolset)
ApprovalCheckFunc = Callable[
    [RunContext[Any], ToolDefinition, dict[str, Any]],
    bool
]

# Old signature (current)
def check_approval(ctx: ApprovalContext) -> Optional[ApprovalRequest]
```

For toolsets that need rich approval requests (not just bool):

```python
ApprovalRequestFunc = Callable[
    [RunContext[Any], ToolDefinition, dict[str, Any]],
    Optional[ApprovalRequest]
]
```

### 4. Remove Duplicate Code from filesystem_sandbox.py

```python
# llm_do/filesystem_sandbox.py

# Before: 170 lines of inline approval types
class ApprovalContext(BaseModel): ...
class ApprovalRequest(BaseModel): ...
class ApprovalDecision(BaseModel): ...
class ApprovalController: ...
class ApprovalToolsetWrapper: ...

# After: Import from single source
from llm_do.approval import (
    ApprovalContext,
    ApprovalRequest,
    ApprovalDecision,
)
from llm_do.approval_controller import ApprovalController
from llm_do.approval_toolset import ApprovalToolset
```

## File Structure After Redesign

```
llm_do/
├── approval.py              # NEW: Core types only (ApprovalContext, Request, Decision)
├── approval_controller.py   # NEW: ApprovalController class
├── approval_toolset.py      # NEW: ApprovalToolset wrapper
├── approval_decorator.py    # NEW: @requires_approval decorator
├── tool_approval.py         # DEPRECATED: Re-exports for backwards compat
├── filesystem_sandbox.py    # MODIFIED: Remove inline types, import from approval.*
├── ...
```

Or simpler flat structure:

```
llm_do/
├── approval.py              # Everything: types, controller, toolset, decorator
├── tool_approval.py         # DEPRECATED: from .approval import *
├── filesystem_sandbox.py    # Import from approval.py
├── ...
```

## Migration Steps

### Phase 1: Extract Types (Non-breaking)

1. Create `llm_do/approval.py` with core types
2. Update `tool_approval.py` to re-export from `approval.py`
3. Update `filesystem_sandbox.py` to import from `approval.py`
4. Remove duplicate type definitions
5. Run tests

### Phase 2: Simplify Wrapper (Non-breaking)

1. Replace manual delegation with `__getattr__`
2. Keep same public API
3. Run tests

### Phase 3: Unified Check Signature (Breaking)

1. Update `check_approval()` signature to match PydanticAI
2. Update `FileSandboxImpl.check_approval()`
3. Update `@requires_approval` decorator
4. Update tests

### Phase 4: Cleanup (Breaking)

1. Remove `tool_approval.py` (after deprecation period)
2. Update all imports to use `approval.py`
3. Remove backwards-compat code

## What We Keep

- **Synchronous blocking pattern** - right for CLI
- **Session caching** - "approve for session" is valuable
- **ApprovalController modes** - interactive/approve_all/strict
- **Rich presentation support** - diffs, syntax highlighting
- **@requires_approval decorator** - convenient for function tools

## What We Remove

- **Duplicate types in filesystem_sandbox.py** - ~170 lines
- **Manual wrapper delegation** - ~30 lines
- **Dual ApprovalController implementations** - ~80 lines

## Estimated Impact

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Lines in tool_approval.py | 524 | ~200 | -62% |
| Lines in filesystem_sandbox.py | 911 | ~750 | -18% |
| Duplicate type definitions | 2 | 1 | -50% |
| Wrapper delegation methods | 8 | 1 | -87% |

## Open Questions

1. **Keep tool_approval.py as re-export layer?** For backwards compat, or force migration?

2. **Align with PydanticAI signature exactly?** Their `approval_func(ctx, tool_def, args) -> bool` vs our `check_approval(ctx) -> Optional[ApprovalRequest]`. Ours is richer but different.

## References

- Current implementation: `llm_do/tool_approval.py`
- Current sandbox: `llm_do/filesystem_sandbox.py`
- PydanticAI toolsets: https://ai.pydantic.dev/toolsets/
- PydanticAI deferred tools: https://ai.pydantic.dev/deferred-tools/
