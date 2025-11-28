# Tool Approval Redesign

**Status:** Phase 0 Complete
**Date:** 2025-11-28

## Completed: Phase 0 - Remove Legacy Callback Pattern

The legacy `ApprovalCallback` pattern has been removed:

- `run_worker()` now accepts `approval_controller: ApprovalController` directly
- Removed `ApprovalCallback` type alias and `approve_all_callback`/`strict_mode_callback` functions
- Removed `get_legacy_callback()` method from `ApprovalController`
- CLI now creates `ApprovalController` directly instead of building callbacks
- Worker delegation passes controllers directly (no more round-trip conversion)

This eliminates the wasteful conversion chain that was:
```
CLI callback -> ApprovalController -> get_legacy_callback() -> child's ApprovalController
```

Now it's simply:
```
CLI ApprovalController -> child inherits same controller
```

---

## Summary

Keep the synchronous blocking wrapper approach for tool approval. After evaluating PydanticAI's deferred pattern (`DeferredToolRequests`/`DeferredToolResults`), we concluded it doesn't fit our CLI use case well. Simplify the existing blocking implementation instead.

## Background

### PydanticAI's Deferred Pattern

PydanticAI v1.0+ provides `ApprovalRequired` exception and `ApprovalRequiredToolset` for human-in-the-loop approval. These use a **deferred pattern**:

```python
result = agent.run_sync(prompt)
if isinstance(result.output, DeferredToolRequests):
    # Agent has stopped - collect approvals
    approvals = collect_approvals(result.output)
    # Resume with new run
    result = agent.run_sync(
        message_history=result.all_messages(),
        deferred_tool_results=approvals,
    )
```

### Why Deferred Doesn't Fit

The deferred pattern is designed for:
- **External async operations** - call an API, wait for webhook hours later
- **Out-of-band approval** - a different person/system approves later
- **Batch processing** - collect multiple deferrals, handle elsewhere

Our CLI use case is different:
- **Synchronous interaction** - user is right there at the terminal
- **Immediate feedback** - approval/rejection happens in real-time
- **Conversational flow** - rejection is just user feedback the LLM should respond to

The deferred pattern adds unnecessary friction:
1. Multiple agent runs with manual message history passing
2. The "loop" is really just a conversation, not a retry mechanism
3. When user denies, the LLM should naturally adjust - that's normal conversation

### The Right Model for CLI

What we actually want:

```
LLM: "I'll write to config.json"
     ↓
Tool blocks for approval
     ↓
User: [approves] → tool executes → LLM continues
      [denies]  → tool returns error → LLM sees error and adjusts
```

This is a single continuous conversation. Denial is just an error the LLM handles like any tool failure - it can retry differently, ask for clarification, or give up gracefully.

**Decision:** Keep synchronous blocking wrapper. Simplify the implementation.

## Current Problems

### 1. Duplicate Type Definitions

Types duplicated in `tool_approval.py` and `filesystem_sandbox.py` (~170 lines).

### 2. Wrapper Boilerplate

`ApprovalToolset` manually delegates every `AbstractToolset` method (~50 lines of delegation).

### 3. Two Integration Patterns

Function tools use `@requires_approval` decorator, class toolsets use `check_approval()` method.

## Proposed Design

### Simplified Blocking Wrapper

```python
class ApprovalToolset(AbstractToolset):
    """Wraps a toolset with synchronous approval checking."""

    def __init__(
        self,
        inner: AbstractToolset,
        prompt_fn: Callable[[ApprovalRequest], ApprovalDecision],
        memory: ApprovalMemory | None = None,
    ):
        self._inner = inner
        self._prompt_fn = prompt_fn
        self._memory = memory or ApprovalMemory()

    def __getattr__(self, name: str) -> Any:
        """Forward unknown attributes to inner toolset."""
        return getattr(self._inner, name)

    async def call_tool(self, name: str, args: dict, ctx: Any, tool: Any) -> Any:
        """Intercept tool calls for approval."""
        request = self._check_approval(name, args)
        if request is not None:
            decision = self._get_approval(request)
            if not decision.approved:
                raise PermissionError(f"User denied {name}: {decision.note or 'no reason given'}")

        return await self._inner.call_tool(name, args, ctx, tool)

    def _check_approval(self, name: str, args: dict) -> ApprovalRequest | None:
        """Check if tool call needs approval."""
        if hasattr(self._inner, "check_approval"):
            return self._inner.check_approval(name, args)
        return None

    def _get_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Get approval from cache or prompt user."""
        # Check session cache
        cached = self._memory.lookup(request.tool_name, request.payload)
        if cached is not None:
            return cached

        # Prompt user (blocks) - receives full request for rich display
        decision = self._prompt_fn(request)

        # Cache if requested
        self._memory.store(request.tool_name, request.payload, decision)

        return decision
```

### Core Types

```python
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

@dataclass
class ApprovalPresentation:
    """Rich presentation data for approval UI.

    Optional - tools can provide this for enhanced display (diffs, syntax highlighting).
    If not provided, the approval prompt renders from tool_name + args.
    """
    type: Literal["text", "diff", "file_content", "command", "structured"]
    content: str
    language: str | None = None  # For syntax highlighting
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRequest:
    """Returned by check_approval() when approval is needed."""
    tool_name: str
    description: str
    payload: dict[str, Any]  # For session matching
    presentation: ApprovalPresentation | None = None  # Rich UI hints


@dataclass
class ApprovalDecision:
    """User's decision about a tool call."""
    approved: bool
    note: str | None = None
    remember: Literal["none", "session"] = "none"


@dataclass
class ApprovalMemory:
    """Session cache to avoid re-prompting for identical calls."""
    _cache: dict[tuple[str, str], ApprovalDecision] = field(default_factory=dict)

    def lookup(self, tool_name: str, args: dict) -> ApprovalDecision | None:
        key = self._make_key(tool_name, args)
        return self._cache.get(key)

    def store(self, tool_name: str, args: dict, decision: ApprovalDecision) -> None:
        if decision.remember == "none":
            return
        key = self._make_key(tool_name, args)
        self._cache[key] = decision

    @staticmethod
    def _make_key(tool_name: str, args: dict) -> tuple[str, str]:
        import json
        return (tool_name, json.dumps(args, sort_keys=True, default=str))
```

### Toolset Protocol

```python
class ApprovalAware(Protocol):
    """Protocol for toolsets that support approval checking."""

    def check_approval(self, tool_name: str, args: dict) -> ApprovalRequest | None:
        """Return ApprovalRequest if approval needed, None otherwise.

        This allows tools to provide rich presentation (diffs, syntax highlighting)
        for the approval prompt.
        """
        ...
```

### Function Decorator (Option C - Marker Only)

For standalone tool functions, `@requires_approval` is simplified to just a marker:

```python
def requires_approval(func: Callable) -> Callable:
    """Mark a function as requiring approval.

    This is a simple marker - no configuration. The ApprovalToolset wrapper
    detects this marker and creates a basic ApprovalRequest from the
    function name and args.
    """
    func._requires_approval = True
    return func
```

Usage:

```python
@requires_approval
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email - always requires approval."""
    return f"Email sent to {to}"

@requires_approval
def delete_file(path: str) -> str:
    """Delete a file - always requires approval."""
    ...
```

The `ApprovalToolset` wrapper detects the marker and creates a basic request:

```python
async def call_tool(self, name: str, args: dict, ctx: Any, tool: Any) -> Any:
    # Check for decorated functions
    if getattr(tool.function, "_requires_approval", False):
        request = ApprovalRequest(
            tool_name=name,
            description=f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())})",
            payload=args,
        )
        decision = self._get_approval(request)
        if not decision.approved:
            raise PermissionError(f"User denied {name}: {decision.note or 'no reason given'}")

    # Check for approval-aware toolsets
    elif hasattr(self._inner, "check_approval"):
        request = self._inner.check_approval(name, args)
        if request is not None:
            decision = self._get_approval(request)
            if not decision.approved:
                raise PermissionError(f"User denied {name}: {decision.note or 'no reason given'}")

    return await self._inner.call_tool(name, args, ctx, tool)
```

**Why marker-only?**

- Simple functions rarely need rich presentation (no diffs, just args)
- Description can be auto-generated from function name + args
- Payload defaults to full args (good enough for most cases)
- Class toolsets that need rich presentation use `check_approval()` directly

### CLI Prompt Function

```python
def cli_prompt(request: ApprovalRequest) -> ApprovalDecision:
    """Prompt user for approval in terminal."""
    print(f"\n🔒 APPROVAL REQUIRED: {request.tool_name}")
    print(f"   {request.description}")

    # Use rich presentation if available
    if request.presentation:
        if request.presentation.type == "diff":
            # Show syntax-highlighted diff
            print_diff(request.presentation.content)
        elif request.presentation.type == "file_content":
            # Show with syntax highlighting
            print_code(request.presentation.content, request.presentation.language)
        else:
            print(request.presentation.content)
    else:
        # Fallback to payload display
        print(f"   Args: {request.payload}")

    print()
    print("[a] Approve once")
    print("[s] Approve for session")
    print("[d] Deny")

    while True:
        choice = input("Choice: ").strip().lower()
        if choice == "a":
            return ApprovalDecision(approved=True)
        elif choice == "s":
            return ApprovalDecision(approved=True, remember="session")
        elif choice == "d":
            reason = input("Reason (optional): ").strip() or None
            return ApprovalDecision(approved=False, note=reason)
```

### Usage

```python
# Setup
sandbox = FileSandboxImpl(config)
memory = ApprovalMemory()

approved_sandbox = ApprovalToolset(
    inner=sandbox,
    prompt_fn=cli_prompt,
    memory=memory,
)

agent = Agent(
    "openai:gpt-4",
    toolsets=[approved_sandbox],
)

# Single continuous run - approvals happen inline
result = agent.run_sync("Create a summary in output.txt")
```

### What Happens on Denial

```
User: "Delete the .env file"

LLM: Calls write_file(path=".env", content="")
     ↓
ApprovalToolset: Prompts user
     ↓
User: Denies with "Don't touch env files"
     ↓
ApprovalToolset: Raises PermissionError("User denied write_file: Don't touch env files")
     ↓
LLM: Sees error, responds naturally:
     "I understand, I won't modify .env. Is there something else I can help with?"
```

The denial flows through as a `PermissionError`. The LLM handles it like any other failure.

## File Structure After Redesign

```
llm_do/
├── tool_approval.py         # SIMPLIFIED
│   ├── ApprovalPresentation # Rich UI hints (diffs, syntax highlighting)
│   ├── ApprovalRequest      # Returned by check_approval()
│   ├── ApprovalDecision     # User's decision
│   ├── ApprovalMemory       # Session cache
│   ├── ApprovalToolset      # Blocking wrapper (simplified with __getattr__)
│   ├── ApprovalAware        # Protocol for toolsets
│   └── requires_approval    # Marker decorator for functions
│
├── cli.py                   # cli_prompt() implementation
├── filesystem_sandbox.py    # SIMPLIFIED: Remove inline types, use check_approval()
└── ...
```

## Migration Steps

### Phase 1: Simplify Types

1. Remove duplicate types from `filesystem_sandbox.py`
2. Consolidate to single location in `tool_approval.py`
3. Remove `ApprovalContext` (not needed - just pass tool_name and args directly)

### Phase 2: Simplify Wrapper

1. Replace manual delegation with `__getattr__`
2. Keep `check_approval() -> ApprovalRequest | None` pattern
3. Move prompt logic to injected function that receives full `ApprovalRequest`

### Phase 3: Simplify FileSandbox

1. Keep `check_approval()` method but simplify signature
2. Return `ApprovalRequest` with optional rich `presentation`
3. Remove inline approval controller

## What We Keep

- **Synchronous blocking** - right for CLI, single continuous agent run
- **Session caching** - "approve for session" via `ApprovalMemory`
- **Natural error handling** - denials are `PermissionError`s the LLM responds to
- **`ApprovalRequest`** - needed for session matching via `payload` field
- **`ApprovalPresentation`** - enables rich UI (diffs, syntax highlighting)
- **`check_approval() -> ApprovalRequest | None`** - allows tools to provide rich presentation

## What We Remove

- **`ApprovalController` class** - replaced by simple prompt function + memory
- **`ApprovalContext`** - over-engineered, just pass tool_name and args directly
- **Duplicate types in filesystem_sandbox.py** - ~170 lines
- **Manual wrapper delegation** - ~50 lines

## Estimated Impact

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| tool_approval.py | 524 lines | ~150 lines | -71% |
| filesystem_sandbox.py | 911 lines | ~550 lines | -40% |
| Total approval code | ~700 lines | ~200 lines | -71% |
| Type definitions | 6 types | 4 types | -33% |

## Why Not Deferred Pattern

| Aspect | Deferred | Blocking |
|--------|----------|----------|
| Agent runs | Multiple with message history | Single continuous |
| Denial handling | Explicit in results, model sees on next run | Tool error, model sees immediately |
| Complexity | Loop + history management | Just blocks |
| Fits CLI | Awkward | Natural |
| Fits web/async | Natural | Would need threading |

The deferred pattern makes sense for web apps where approval might come from a different user/session hours later. For an interactive CLI where the user is right there, blocking is simpler and more natural.

## References

- Current implementation: `llm_do/tool_approval.py`
- Current sandbox: `llm_do/filesystem_sandbox.py`
- PydanticAI deferred tools: https://ai.pydantic.dev/deferred-tools/
