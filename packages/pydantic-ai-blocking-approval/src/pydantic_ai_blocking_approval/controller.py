"""ApprovalController for mode-based approval handling.

This module provides ApprovalController, which manages approval modes
and provides prompt functions for use with ApprovalToolset.
"""
from __future__ import annotations

from typing import Callable, Literal, Optional

from .memory import ApprovalMemory
from .types import ApprovalDecision, ApprovalRequest


class ApprovalController:
    """Manages approval mode and provides prompt functions.

    This controller provides mode-based approval handling:

    - **interactive**: Prompts user via callback (blocks until decision)
    - **approve_all**: Auto-approves all requests (for testing)
    - **strict**: Auto-denies all requests (for CI/production safety)

    Example:
        # Auto-approve everything (for tests)
        controller = ApprovalController(mode="approve_all")

        # Reject everything (for CI/production)
        controller = ApprovalController(mode="strict")

        # Interactive mode with custom callback
        def my_callback(request: ApprovalRequest) -> ApprovalDecision:
            # Show UI, get user input
            return ApprovalDecision(approved=True, remember="session")

        controller = ApprovalController(
            mode="interactive",
            approval_callback=my_callback
        )

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
        """Check if this request is already approved for the session.

        Args:
            request: The approval request to check

        Returns:
            True if a matching approval is cached, False otherwise
        """
        cached = self._memory.lookup(request.tool_name, request.payload)
        return cached is not None and cached.approved

    def clear_session_approvals(self) -> None:
        """Clear all session approvals."""
        self._memory.clear()

    def request_approval_sync(self, request: ApprovalRequest) -> ApprovalDecision:
        """Synchronous approval request.

        Handles the request based on the current mode:
        - approve_all: Returns approved=True immediately
        - strict: Returns approved=False with note
        - interactive: Checks cache, then prompts via callback

        Args:
            request: The approval request

        Returns:
            ApprovalDecision with the result

        Raises:
            NotImplementedError: If interactive mode has no callback
        """
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

        Returns:
            A callable that takes ApprovalRequest and returns ApprovalDecision

        Raises:
            RuntimeError: If interactive mode has no callback set
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
