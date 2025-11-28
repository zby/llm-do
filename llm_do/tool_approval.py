"""Tool approval types and utilities.

This module provides the core approval types that are framework-agnostic
and can be used with any LLM agent framework (PydanticAI, LangChain, etc.).

The types defined here are:
- ApprovalPresentation: Rich UI hints for approval display
- ApprovalRequest: Returned by tools to request approval
- ApprovalDecision: Returned after user interaction
- ApprovalMemory: Session cache for "approve for session"
- ApprovalAware: Protocol for tools that support approval
- ApprovalToolset: Wrapper that adds approval to any toolset

See docs/notes/tool_approval_redesign.md for full design details.
"""
from __future__ import annotations

import json
from typing import (
    Any,
    Callable,
    Literal,
    Optional,
    Protocol,
)

from pydantic import BaseModel, Field
from pydantic_ai.toolsets import AbstractToolset


# ---------------------------------------------------------------------------
# Core Types
# ---------------------------------------------------------------------------


class ApprovalPresentation(BaseModel):
    """Rich presentation data for approval UI.

    Optional - tools can provide this for enhanced display (diffs, syntax highlighting).
    If not provided, the approval prompt renders from tool_name + args.
    """

    type: Literal["text", "diff", "file_content", "command", "structured"]
    content: str
    language: Optional[str] = None  # For syntax highlighting
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Returned by check_approval() when approval is needed."""

    tool_name: str
    description: str
    payload: dict[str, Any]  # For session matching
    presentation: Optional[ApprovalPresentation] = None  # Rich UI hints


class ApprovalDecision(BaseModel):
    """User's decision about a tool call."""

    approved: bool
    note: Optional[str] = None
    remember: Literal["none", "session"] = "none"


# ---------------------------------------------------------------------------
# Session Memory
# ---------------------------------------------------------------------------


class ApprovalMemory:
    """Session cache to avoid re-prompting for identical calls."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], ApprovalDecision] = {}

    def lookup(self, tool_name: str, args: dict) -> Optional[ApprovalDecision]:
        """Look up a previous approval decision."""
        key = self._make_key(tool_name, args)
        return self._cache.get(key)

    def store(self, tool_name: str, args: dict, decision: ApprovalDecision) -> None:
        """Store an approval decision for session reuse."""
        if decision.remember == "none":
            return
        key = self._make_key(tool_name, args)
        self._cache[key] = decision

    def clear(self) -> None:
        """Clear all session approvals."""
        self._cache.clear()

    @staticmethod
    def _make_key(tool_name: str, args: dict) -> tuple[str, str]:
        """Create hashable key for session matching."""
        return (tool_name, json.dumps(args, sort_keys=True, default=str))


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class ApprovalAware(Protocol):
    """Protocol for toolsets that support approval checking."""

    def check_approval(
        self, tool_name: str, args: dict, memory: ApprovalMemory
    ) -> Optional[ApprovalRequest]:
        """Return ApprovalRequest if approval needed, None otherwise.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments
            memory: Session approval cache - toolset can check for pattern matches

        This allows tools to:
        - Provide rich presentation (diffs, syntax highlighting)
        - Implement pattern-based session approvals (e.g., "approve all writes to /data")

        Returns:
            None - No approval needed, proceed with execution
            ApprovalRequest - Approval required before execution

        Raises:
            PermissionError - Operation is blocked entirely (not just needs approval)
        """
        ...


# ---------------------------------------------------------------------------
# Decorator (Marker Only)
# ---------------------------------------------------------------------------


def requires_approval(func: Callable) -> Callable:
    """Mark a function as requiring approval.

    This is a simple marker - no configuration. The ApprovalToolset wrapper
    detects this marker and creates a basic ApprovalRequest from the
    function name and args.

    Example:
        @requires_approval
        def send_email(to: str, subject: str, body: str) -> str:
            return f"Email sent to {to}"

        @requires_approval
        def delete_file(path: str) -> str:
            ...
    """
    func._requires_approval = True  # type: ignore[attr-defined]
    return func


# ---------------------------------------------------------------------------
# Approval Toolset Wrapper
# ---------------------------------------------------------------------------


class ApprovalToolset(AbstractToolset):
    """Wraps a toolset with synchronous approval checking.

    Usage:
        sandbox = FileSandboxImpl(config)
        memory = ApprovalMemory()

        approved_sandbox = ApprovalToolset(
            inner=sandbox,
            prompt_fn=cli_prompt,
            memory=memory,
        )
        agent = Agent(..., toolsets=[approved_sandbox])
    """

    def __init__(
        self,
        inner: AbstractToolset,
        prompt_fn: Callable[[ApprovalRequest], ApprovalDecision],
        memory: Optional[ApprovalMemory] = None,
    ):
        """Initialize the approval wrapper.

        Args:
            inner: The toolset to wrap (must implement AbstractToolset)
            prompt_fn: Callback to prompt user for approval (blocks until decision)
            memory: Session cache for "approve for session" (created if None)
        """
        self._inner = inner
        self._prompt_fn = prompt_fn
        self._memory = memory or ApprovalMemory()

    @property
    def id(self) -> Optional[str]:
        """Delegate to inner toolset's id."""
        return getattr(self._inner, "id", None)

    def __getattr__(self, name: str) -> Any:
        """Forward unknown attributes to inner toolset."""
        return getattr(self._inner, name)

    async def get_tools(self, ctx: Any) -> dict:
        """Delegate to inner toolset's get_tools."""
        return await self._inner.get_tools(ctx)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: Any,
    ) -> Any:
        """Intercept tool calls for approval."""
        # Check for decorated functions with @requires_approval marker
        # Handle both plain functions and ToolsetTool objects
        func = getattr(tool, "function", tool)
        if getattr(func, "_requires_approval", False):
            request = ApprovalRequest(
                tool_name=name,
                description=f"{name}({', '.join(f'{k}={v!r}' for k, v in tool_args.items())})",
                payload=tool_args,
            )
            decision = self._get_approval(request)
            if not decision.approved:
                raise PermissionError(
                    f"User denied {name}: {decision.note or 'no reason given'}"
                )

        # Check for approval-aware toolsets
        elif hasattr(self._inner, "check_approval"):
            try:
                # Pass memory so toolset can do pattern-based session checks
                request = self._inner.check_approval(name, tool_args, self._memory)
            except PermissionError:
                # Tool blocked entirely
                raise

            if request is not None:
                decision = self._get_approval(request)
                if not decision.approved:
                    raise PermissionError(
                        f"User denied {name}: {decision.note or 'no reason given'}"
                    )

        return await self._inner.call_tool(name, tool_args, ctx, tool)

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


# ---------------------------------------------------------------------------
# Approval Controller (Compatibility Layer)
# ---------------------------------------------------------------------------


class ApprovalController:
    """Manages approval mode and provides prompt functions.

    This is a compatibility layer that bridges the old API to the new design.
    It provides mode-based prompt functions that can be passed to ApprovalToolset.

    Usage:
        # Auto-approve everything (for tests)
        controller = ApprovalController(mode="approve_all")

        # Reject everything (for CI/production)
        controller = ApprovalController(mode="strict")

        # Interactive mode with custom callback
        def my_callback(request: ApprovalRequest) -> ApprovalDecision:
            # Show UI, get user input
            return ApprovalDecision(approved=True, remember="session")

        controller = ApprovalController(mode="interactive", approval_callback=my_callback)

        # Use with ApprovalToolset
        approved_sandbox = ApprovalToolset(
            inner=sandbox,
            prompt_fn=controller.approval_callback,
            memory=controller.memory,
        )
    """

    def __init__(
        self,
        mode: Literal["interactive", "approve_all", "strict"] = "interactive",
        approval_callback: Optional[Callable[[ApprovalRequest], ApprovalDecision]] = None,
    ):
        """Initialize the approval controller.

        Args:
            mode: Runtime mode for approval handling
            approval_callback: Optional sync callback for prompting user.
                              Required for interactive mode.
        """
        self.mode = mode
        self._approval_callback = approval_callback
        self._memory = ApprovalMemory()

    @property
    def memory(self) -> ApprovalMemory:
        """Get the session memory for caching approvals."""
        return self._memory

    def is_session_approved(self, request: ApprovalRequest) -> bool:
        """Check if this request is already approved for the session."""
        cached = self._memory.lookup(request.tool_name, request.payload)
        return cached is not None and cached.approved

    def clear_session_approvals(self) -> None:
        """Clear all session approvals."""
        self._memory.clear()

    def request_approval_sync(self, request: ApprovalRequest) -> ApprovalDecision:
        """Synchronous approval request (compatibility method)."""
        # Handle non-interactive modes
        if self.mode == "approve_all":
            return ApprovalDecision(approved=True)
        if self.mode == "strict":
            return ApprovalDecision(
                approved=False, note=f"Strict mode: {request.tool_name} requires approval"
            )

        # Check session cache
        cached = self._memory.lookup(request.tool_name, request.payload)
        if cached is not None:
            return cached

        # Prompt user
        if self._approval_callback is None:
            raise NotImplementedError(
                "No approval_callback provided for interactive mode"
            )
        decision = self._approval_callback(request)

        # Cache if remember="session"
        if decision.approved and decision.remember == "session":
            self._memory.store(request.tool_name, request.payload, decision)

        return decision

    @property
    def approval_callback(self) -> Callable[[ApprovalRequest], ApprovalDecision]:
        """Get the approval callback based on mode.

        Returns a prompt function suitable for ApprovalToolset.
        """
        if self._approval_callback is not None:
            return self._approval_callback

        # Return a default callback based on mode
        if self.mode == "approve_all":
            return lambda req: ApprovalDecision(approved=True)
        elif self.mode == "strict":
            return lambda req: ApprovalDecision(
                approved=False,
                note=f"Strict mode: {req.tool_name} requires approval"
            )
        else:
            # Interactive mode with no callback
            raise RuntimeError("No approval_callback set for interactive mode")


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "ApprovalAware",
    "ApprovalController",
    "ApprovalDecision",
    "ApprovalMemory",
    "ApprovalPresentation",
    "ApprovalRequest",
    "ApprovalToolset",
    "requires_approval",
]
