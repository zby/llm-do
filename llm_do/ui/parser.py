"""UI parsing helpers."""
from __future__ import annotations

from typing import Any

from .events import ApprovalRequestEvent


def parse_approval_request(request: Any, *, agent: str) -> ApprovalRequestEvent:
    """Parse an ApprovalRequest into an ApprovalRequestEvent.

    Args:
        request: An ApprovalRequest object from pydantic_ai_blocking_approval
        agent: Agent name for display context

    Returns:
        ApprovalRequestEvent ready for display
    """
    return ApprovalRequestEvent(
        agent=agent,
        tool_name=getattr(request, "tool_name", ""),
        reason=getattr(request, "description", ""),
        args=getattr(request, "tool_args", {}),
        request=request,
    )
