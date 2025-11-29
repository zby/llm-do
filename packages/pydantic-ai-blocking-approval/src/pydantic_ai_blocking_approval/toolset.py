"""ApprovalToolset wrapper for PydanticAI toolsets.

This module provides ApprovalToolset, which wraps any PydanticAI toolset
and intercepts tool calls for approval checking.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from pydantic_ai.toolsets import AbstractToolset

from .memory import ApprovalMemory
from .types import ApprovalDecision, ApprovalRequest


class ApprovalToolset(AbstractToolset):
    """Wraps a toolset with synchronous approval checking.

    This wrapper intercepts all tool calls and checks if approval is needed
    before delegating to the inner toolset. It supports two patterns:

    1. **@requires_approval decorator**: Functions marked with the decorator
       will always prompt for approval.

    2. **ApprovalAware protocol**: Toolsets implementing `check_approval()`
       can provide custom approval logic with rich presentation.

    The wrapper blocks execution until the user decides (via prompt_fn),
    making it suitable for CLI/interactive use where the user is present.

    Example:
        from pydantic_ai import Agent
        from pydantic_ai_blocking_approval import ApprovalToolset, ApprovalMemory

        sandbox = FileSandboxImpl(config)
        memory = ApprovalMemory()

        def cli_prompt(request: ApprovalRequest) -> ApprovalDecision:
            # Show UI, get user input
            return ApprovalDecision(approved=True, remember="session")

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
        """Intercept tool calls for approval.

        Checks for approval in this order:
        1. If tool has @requires_approval marker, create basic request
        2. If inner toolset has check_approval(), call it for custom logic
        3. Otherwise, proceed without approval

        Args:
            name: Tool name being called
            tool_args: Arguments passed to the tool
            ctx: PydanticAI run context
            tool: The tool object/function

        Returns:
            Result from the inner toolset's call_tool

        Raises:
            PermissionError: If user denies approval or toolset blocks operation
        """
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
        """Get approval from cache or prompt user.

        Args:
            request: The approval request

        Returns:
            ApprovalDecision from cache or user prompt
        """
        # Check session cache
        cached = self._memory.lookup(request.tool_name, request.payload)
        if cached is not None:
            return cached

        # Prompt user (blocks) - receives full request for rich display
        decision = self._prompt_fn(request)

        # Cache if requested
        self._memory.store(request.tool_name, request.payload, decision)

        return decision
