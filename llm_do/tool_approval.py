"""Tool approval types and utilities.

This module provides the core approval types that are framework-agnostic
and can be used with any LLM agent framework (PydanticAI, LangChain, etc.).

The types defined here are:
- ApprovalPresentation: Rich UI hints for approval display
- ApprovalContext: Context passed to check_approval()
- ApprovalRequest: Returned by tools to request approval
- ApprovalDecision: Returned by controller after user interaction
- ApprovalAware: Protocol for tools that support approval

See docs/design/tool_approval_architecture.md for full design details.
"""
from __future__ import annotations

import functools
from typing import (
    Any,
    Callable,
    Literal,
    Optional,
    Protocol,
    Union,
)

from pydantic import BaseModel, Field
from pydantic_ai.toolsets import AbstractToolset


# ---------------------------------------------------------------------------
# Core Types
# ---------------------------------------------------------------------------


class ApprovalPresentation(BaseModel):
    """Rich presentation data for approval UI.

    This is optional—tools can return just the basic ApprovalRequest fields
    and let the approval controller generate presentation from the payload.
    """

    type: Literal["text", "diff", "file_content", "command", "structured"]
    content: str
    language: Optional[str] = None  # For syntax highlighting
    metadata: dict[str, Any] = Field(default_factory=dict)  # e.g., {"full_content": "..."} for pager


class ApprovalContext(BaseModel):
    """Context passed to check_approval.

    The core fields (tool_name, args) are framework-agnostic. The metadata
    dict allows framework-specific data (run IDs, session IDs, caller info)
    without polluting the base interface.
    """

    tool_name: str
    args: dict[str, Any]

    # Framework-specific context goes here (run_id, session_id, caller, etc.)
    # This keeps the core interface stable across different agent frameworks.
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Returned by a tool to request approval before execution.

    This is the single canonical shape for all approval requests.
    The payload field is the structured fingerprint used for session
    approval matching—tools control what goes here.
    """

    # Stable identifier: what the operator sees and what gets logged
    tool_name: str
    description: str

    # Structured fingerprint for "approve for session" matching.
    # Tools control what goes here (can omit secrets, normalize paths, etc.)
    payload: dict[str, Any]

    # Optional rich UI hints. If None, the approval controller renders
    # a default display from tool_name + payload.
    presentation: Optional[ApprovalPresentation] = None

    # Optional grouping for batch approvals
    group_id: Optional[str] = None


class ApprovalDecision(BaseModel):
    """Returned by the approval controller after user interaction."""

    approved: bool
    scope: Literal["once", "session"] = "once"  # "session" means don't prompt again
    note: Optional[str] = None  # Reason for rejection, or user comment


class ApprovalAware(Protocol):
    """Protocol for tools that can request approval.

    This is intentionally synchronous. Approval checking should be a fast,
    pure computation based on tool config and arguments. Any I/O-heavy work
    (like generating diffs for presentation) should be done lazily by the
    approval controller, not in check_approval().
    """

    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Inspect context and return approval request, or None if no approval needed.

        Returns:
            None - No approval needed, proceed with execution
            ApprovalRequest - Approval required before execution

        Raises:
            PermissionError - Operation is blocked entirely (not just needs approval)
        """
        ...


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------


def simple_approval_request(
    tool_name: str,
    args: dict[str, Any],
    *,
    description: Optional[str] = None,
    exclude_keys: Optional[set[str]] = None,
) -> ApprovalRequest:
    """Create an ApprovalRequest with sensible defaults.

    Args:
        tool_name: Name of the tool requesting approval
        args: Tool arguments
        description: Human-readable description. If None, auto-generated from tool_name and args.
        exclude_keys: Keys to omit from payload (e.g., large content, secrets)

    Returns:
        ApprovalRequest ready to return from check_approval()
    """
    # Build payload, optionally excluding certain keys
    if exclude_keys:
        payload = {k: v for k, v in args.items() if k not in exclude_keys}
    else:
        payload = dict(args)

    # Auto-generate description if not provided
    if description is None:
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        description = f"{tool_name}({args_str})"

    return ApprovalRequest(
        tool_name=tool_name,
        description=description,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def requires_approval(
    *,
    description: Union[str, Callable[[dict[str, Any]], str], None] = None,
    exclude_keys: Optional[set[str]] = None,
    payload: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> Callable[[Callable], Callable]:
    """Decorator that adds check_approval() to a tool function.

    Args:
        description: Static string or callable that generates description from args.
                    If None, auto-generates from function name and args.
        exclude_keys: Keys to exclude from auto-generated payload.
        payload: Custom payload generator. If provided, exclude_keys is ignored.

    Example:
        @requires_approval()
        def delete_file(path: str) -> str:
            ...

        @requires_approval(
            description=lambda args: f"Delete {args['path']}",
            exclude_keys={"force"},
        )
        def delete_file(path: str, force: bool = False) -> str:
            ...
    """

    def decorator(func: Callable) -> Callable:
        tool_name = func.__name__

        def check_approval(ctx: ApprovalContext) -> Optional[ApprovalRequest]:
            # Generate description
            if description is None:
                args_str = ", ".join(f"{k}={v!r}" for k, v in ctx.args.items())
                desc = f"{tool_name}({args_str})"
            elif callable(description):
                desc = description(ctx.args)
            else:
                desc = description

            # Generate payload
            if payload is not None:
                pl = payload(ctx.args)
            elif exclude_keys:
                pl = {k: v for k, v in ctx.args.items() if k not in exclude_keys}
            else:
                pl = dict(ctx.args)

            return ApprovalRequest(
                tool_name=tool_name,
                description=desc,
                payload=pl,
            )

        # Attach check_approval to the function
        func.check_approval = check_approval  # type: ignore[attr-defined]

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # Also attach to wrapper so it's preserved
        wrapper.check_approval = check_approval  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Approval Controller
# ---------------------------------------------------------------------------


class ApprovalController:
    """Manages approval requests, session memory, and user prompts.

    This is the framework-agnostic approval controller. It handles:
    - Runtime mode interpretation (interactive, approve_all, strict)
    - Session approval caching
    - Lazy presentation generation
    - User prompt dispatch (via subclass or callback)
    """

    def __init__(
        self,
        mode: Literal["interactive", "approve_all", "strict"] = "interactive",
        approval_callback: Optional[
            Callable[[ApprovalRequest], ApprovalDecision]
        ] = None,
    ):
        """Initialize the approval controller.

        Args:
            mode: Runtime mode for approval handling
            approval_callback: Optional sync callback for prompting user.
                              If None, request_approval will raise NotImplementedError
                              for interactive mode.
        """
        self.mode = mode
        self._approval_callback = approval_callback
        self._session_approvals: set[tuple[str, frozenset]] = set()

    @property
    def approval_callback(self) -> Callable[[ApprovalRequest], ApprovalDecision]:
        """Get the approval callback, or a default based on mode.

        This is used when delegating to child workers to create their controller.
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
            # Interactive mode with no callback - this shouldn't be used
            raise RuntimeError("No approval_callback set for interactive mode")

    def _make_key(self, request: ApprovalRequest) -> tuple[str, frozenset]:
        """Create hashable key for session matching."""

        def freeze(obj: Any) -> Any:
            if isinstance(obj, dict):
                return frozenset((k, freeze(v)) for k, v in sorted(obj.items()))
            elif isinstance(obj, (list, tuple)):
                return tuple(freeze(x) for x in obj)
            return obj

        return (request.tool_name, freeze(request.payload))

    def is_session_approved(self, request: ApprovalRequest) -> bool:
        """Check if this request is already approved for the session."""
        return self._make_key(request) in self._session_approvals

    def add_session_approval(self, request: ApprovalRequest) -> None:
        """Add a request to the session approval cache."""
        self._session_approvals.add(self._make_key(request))

    def clear_session_approvals(self) -> None:
        """Clear all session approvals."""
        self._session_approvals.clear()

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Main entry point for approval requests.

        This handles mode interpretation, session caching, and user prompts.
        """
        # 1. Handle non-interactive modes first (no I/O needed)
        if self.mode == "approve_all":
            return ApprovalDecision(approved=True)
        if self.mode == "strict":
            return ApprovalDecision(
                approved=False, note="Strict mode: approval required"
            )

        # 2. Check session cache BEFORE prompting
        if self.is_session_approved(request):
            return ApprovalDecision(approved=True, scope="session")

        # 3. Prompt the user
        if self._approval_callback is None:
            raise NotImplementedError(
                "No approval_callback provided for interactive mode"
            )

        # Call the callback (may be sync or async)
        decision = self._approval_callback(request)

        # 4. Update session cache if user chose "approve for session"
        if decision.approved and decision.scope == "session":
            self.add_session_approval(request)

        return decision

    def request_approval_sync(self, request: ApprovalRequest) -> ApprovalDecision:
        """Synchronous version of request_approval for non-async contexts."""
        # For non-interactive modes, we can handle synchronously
        if self.mode == "approve_all":
            return ApprovalDecision(approved=True)
        if self.mode == "strict":
            return ApprovalDecision(
                approved=False, note="Strict mode: approval required"
            )

        if self.is_session_approved(request):
            return ApprovalDecision(approved=True, scope="session")

        if self._approval_callback is None:
            raise NotImplementedError(
                "No approval_callback provided for interactive mode"
            )

        decision = self._approval_callback(request)

        if decision.approved and decision.scope == "session":
            self.add_session_approval(request)

        return decision


# ---------------------------------------------------------------------------
# Approval Toolset Wrapper
# ---------------------------------------------------------------------------


class ApprovalToolset(AbstractToolset):
    """Wraps a PydanticAI toolset with approval checking.

    This implements the composition pattern (Option C) from the design doc:
    - The inner toolset handles actual tool execution
    - This wrapper intercepts calls to check approval first
    - If the inner toolset implements check_approval, it's called
    - The approval controller decides whether to proceed

    Usage:
        sandbox = FileSandboxImpl(config)
        controller = ApprovalController(mode="interactive", approval_callback=...)
        approval_sandbox = ApprovalToolset(sandbox, controller)
        agent = Agent(..., toolsets=[approval_sandbox])
    """

    def __init__(
        self,
        inner: AbstractToolset,
        controller: ApprovalController,
    ):
        """Initialize the approval wrapper.

        Args:
            inner: The toolset to wrap (must implement AbstractToolset)
            controller: Approval controller for handling approval requests
        """
        self._inner = inner
        self._controller = controller

    @property
    def id(self) -> Optional[str]:
        """Delegate to inner toolset's id."""
        return getattr(self._inner, "id", None)

    @property
    def label(self) -> str:
        """The name of the toolset for use in error messages."""
        return getattr(self._inner, "label", self.__class__.__name__)

    @property
    def tool_name_conflict_hint(self) -> str:
        """Delegate to inner toolset."""
        return getattr(
            self._inner,
            "tool_name_conflict_hint",
            "Rename the tool or wrap the toolset in a `PrefixedToolset` to avoid name conflicts.",
        )

    async def __aenter__(self) -> "ApprovalToolset":
        """Enter the toolset context."""
        if hasattr(self._inner, "__aenter__"):
            await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> Optional[bool]:
        """Exit the toolset context."""
        if hasattr(self._inner, "__aexit__"):
            return await self._inner.__aexit__(*args)
        return None

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
        """Call tool with approval checking.

        This is where the approval magic happens:
        1. Build ApprovalContext from the call
        2. Call inner.check_approval() if it exists
        3. If approval needed, ask the controller
        4. If approved (or no approval needed), call the actual tool
        """
        # 1. Check if inner toolset is approval-aware
        if hasattr(self._inner, "check_approval"):
            approval_ctx = ApprovalContext(
                tool_name=name,
                args=tool_args,
                metadata={
                    "toolset_id": self.id,
                },
            )

            try:
                # check_approval is sync
                approval_request = self._inner.check_approval(approval_ctx)
            except PermissionError:
                # Tool blocked entirely
                raise

            if approval_request is not None:
                # 2. Ask approval controller
                decision = await self._controller.request_approval(approval_request)

                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"Approval denied for {name}{note}")

        # 3. Execute the actual tool
        return await self._inner.call_tool(name, tool_args, ctx, tool)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "ApprovalAware",
    "ApprovalContext",
    "ApprovalController",
    "ApprovalDecision",
    "ApprovalPresentation",
    "ApprovalRequest",
    "ApprovalToolset",
    "requires_approval",
    "simple_approval_request",
]
