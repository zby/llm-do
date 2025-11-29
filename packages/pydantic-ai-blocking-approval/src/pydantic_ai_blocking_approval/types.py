"""Core approval types.

This module defines the fundamental data types for the blocking approval system:
- ApprovalPresentation: Rich UI hints for approval display
- ApprovalRequest: Returned by tools to request approval
- ApprovalDecision: User's decision about a tool call
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ApprovalPresentation(BaseModel):
    """Rich presentation data for approval UI.

    Optional - tools can provide this for enhanced display (diffs, syntax highlighting).
    If not provided, the approval prompt renders from tool_name + args.

    Attributes:
        type: The presentation type determining how content should be rendered
        content: The actual content to display
        language: Optional language hint for syntax highlighting
        metadata: Additional presentation metadata
    """

    type: Literal["text", "diff", "file_content", "command", "structured"]
    content: str
    language: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Returned by check_approval() when approval is needed.

    This is the primary type returned by tools or toolsets when they need
    user approval before proceeding with an operation.

    Attributes:
        tool_name: Name of the tool requesting approval
        description: Human-readable description of what the tool wants to do
        payload: Data for session matching (determines if cached approval applies)
        presentation: Optional rich UI hints for enhanced display
    """

    tool_name: str
    description: str
    payload: dict[str, Any]
    presentation: Optional[ApprovalPresentation] = None


class ApprovalDecision(BaseModel):
    """User's decision about a tool call.

    Returned after the user (or auto-mode) decides whether to approve
    a tool operation.

    Attributes:
        approved: Whether the operation should proceed
        note: Optional reason for rejection or comment
        remember: Whether to cache this decision for the session
    """

    approved: bool
    note: Optional[str] = None
    remember: Literal["none", "session"] = "none"
