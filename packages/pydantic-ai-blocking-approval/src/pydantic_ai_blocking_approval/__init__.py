"""Synchronous, blocking approval system for PydanticAI agent tools.

This package provides human-in-the-loop approval handling for LLM agent tools.
Unlike deferred/async approval patterns, this system blocks execution until
the user decides, making it ideal for CLI and interactive use cases where
the user is present at the terminal.

Key Components:
    - ApprovalRequest: Returned by tools when approval is needed
    - ApprovalDecision: User's decision (approved, remember for session)
    - ApprovalMemory: Session cache for "approve for session" functionality
    - ApprovalToolset: Wrapper that intercepts tool calls for approval
    - ApprovalController: Mode-based controller (interactive/approve_all/strict)
    - @requires_approval: Simple decorator to mark functions needing approval

Example:
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

For testing, use approve_all or strict modes:
    controller = ApprovalController(mode="approve_all")  # Auto-approve
    controller = ApprovalController(mode="strict")       # Auto-deny
"""

from .controller import ApprovalController
from .decorator import requires_approval
from .memory import ApprovalMemory
from .protocol import ApprovalAware
from .toolset import ApprovalToolset
from .types import ApprovalDecision, ApprovalPresentation, ApprovalRequest

__version__ = "0.1.0"

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
