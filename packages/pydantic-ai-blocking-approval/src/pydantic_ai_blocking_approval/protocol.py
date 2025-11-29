"""Protocol for approval-aware toolsets.

This module defines the ApprovalAware protocol that toolsets can implement
to provide custom approval logic.
"""
from __future__ import annotations

from typing import Optional, Protocol

from .memory import ApprovalMemory
from .types import ApprovalRequest


class ApprovalAware(Protocol):
    """Protocol for toolsets that support approval checking.

    Toolsets implementing this protocol can provide custom logic for:
    - Determining which operations need approval
    - Generating rich presentation data (diffs, syntax highlighting)
    - Pattern-based session matching (e.g., "approve all writes to /data")

    Example:
        class MyToolset:
            def check_approval(
                self, tool_name: str, args: dict, memory: ApprovalMemory
            ) -> Optional[ApprovalRequest]:
                if tool_name == "dangerous_operation":
                    return ApprovalRequest(
                        tool_name=tool_name,
                        description="Execute dangerous operation",
                        payload=args,
                    )
                return None  # No approval needed
    """

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
        - Implement pattern-based session approvals

        Returns:
            None - No approval needed, proceed with execution
            ApprovalRequest - Approval required before execution

        Raises:
            PermissionError - Operation is blocked entirely (not just needs approval)
        """
        ...
