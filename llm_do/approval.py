"""Approval enforcement for tool calls.

This module provides the ApprovalController class which enforces
tool rules and prompts for user approval when required.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Set, Tuple

from .types import ApprovalCallback, approve_all_callback


class ApprovalController:
    """Apply tool rules with blocking approval prompts."""

    def __init__(
        self,
        tool_rules: Mapping[str, Any],  # ToolRule from types
        *,
        approval_callback: ApprovalCallback = approve_all_callback,
    ):
        self.tool_rules = tool_rules
        self.approval_callback = approval_callback
        self.session_approvals: Set[Tuple[str, frozenset]] = set()

    def _make_approval_key(
        self, tool_name: str, payload: Mapping[str, Any]
    ) -> Tuple[str, frozenset]:
        """Create a hashable key for session approval tracking."""
        try:
            items = frozenset(payload.items())
        except TypeError:
            # If payload has unhashable values, use repr as fallback
            items = frozenset((k, repr(v)) for k, v in payload.items())
        return (tool_name, items)

    def maybe_run(
        self,
        tool_name: str,
        payload: Mapping[str, Any],
        func: Callable[[], Any],
    ) -> Any:
        """Check approval rules and execute function if approved.

        Args:
            tool_name: Name of the tool being called
            payload: Arguments passed to the tool
            func: Function to execute if approved

        Returns:
            Result of func() if approved

        Raises:
            PermissionError: If tool is disallowed or user rejects
        """
        rule = self.tool_rules.get(tool_name)
        if rule:
            if not rule.allowed:
                raise PermissionError(f"Tool '{tool_name}' is disallowed")
            if rule.approval_required:
                # Check session approvals
                key = self._make_approval_key(tool_name, payload)
                if key in self.session_approvals:
                    return func()

                # Block and wait for approval
                decision = self.approval_callback(tool_name, payload, rule.description)
                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"User rejected tool call '{tool_name}'{note}")

                # Track session approval if requested
                if decision.scope == "session":
                    self.session_approvals.add(key)

        return func()
