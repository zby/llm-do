"""Tool approval types and utilities.

This module re-exports from pydantic-ai-blocking-approval for backward compatibility.
All types and utilities are now provided by the standalone package.

See docs/notes/tool_approval_redesign.md for full design details.
"""

# Re-export everything from the standalone package
from pydantic_ai_blocking_approval import (
    ApprovalAware,
    ApprovalController,
    ApprovalDecision,
    ApprovalMemory,
    ApprovalPresentation,
    ApprovalRequest,
    ApprovalToolset,
    requires_approval,
)

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
