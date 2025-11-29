"""Decorator for marking functions as requiring approval.

This module provides the @requires_approval decorator, a simple marker
that indicates a function needs user approval before execution.
"""
from __future__ import annotations

from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def requires_approval(func: F) -> F:
    """Mark a function as requiring approval.

    This is a simple marker decorator - no configuration. The ApprovalToolset
    wrapper detects this marker and creates a basic ApprovalRequest from the
    function name and args.

    Example:
        @requires_approval
        def send_email(to: str, subject: str, body: str) -> str:
            return f"Email sent to {to}"

        @requires_approval
        def delete_file(path: str) -> str:
            os.remove(path)
            return f"Deleted {path}"

    The decorated function can be used normally - the approval check happens
    at the toolset wrapper level, not in the function itself.
    """
    func._requires_approval = True  # type: ignore[attr-defined]
    return func
