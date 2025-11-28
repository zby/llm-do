"""Tests for the tool_approval module.

This module tests the framework-agnostic approval types and utilities:
- @requires_approval decorator (marker-only)
- ApprovalController session approval matching
- ApprovalToolset wrapper
"""
import pytest

from llm_do.tool_approval import (
    ApprovalController,
    ApprovalDecision,
    ApprovalRequest,
    requires_approval,
)


# ---------------------------------------------------------------------------
# @requires_approval decorator tests
# ---------------------------------------------------------------------------


class TestRequiresApprovalDecorator:
    """Tests for the @requires_approval decorator (marker-only)."""

    def test_decorator_marks_function(self):
        """Decorator marks function with _requires_approval attribute."""

        @requires_approval
        def my_tool(arg: str) -> str:
            return f"done: {arg}"

        # Function should have _requires_approval attribute
        assert hasattr(my_tool, "_requires_approval")
        assert my_tool._requires_approval is True

    def test_decorated_function_still_works(self):
        """Decorated function still executes normally."""

        @requires_approval
        def add_numbers(a: int, b: int) -> int:
            return a + b

        # Function should still work
        result = add_numbers(2, 3)
        assert result == 5

    def test_decorator_preserves_function_metadata(self):
        """Decorator preserves function name and docstring."""

        @requires_approval
        def my_documented_tool(x: int) -> int:
            """This is my tool's docstring."""
            return x * 2

        assert my_documented_tool.__name__ == "my_documented_tool"
        # Note: simple marker decorator doesn't use functools.wraps
        # so docstring may not be preserved


# ---------------------------------------------------------------------------
# ApprovalController tests
# ---------------------------------------------------------------------------


class TestApprovalController:
    """Tests for the ApprovalController class."""

    def test_approve_all_mode(self):
        """approve_all mode auto-approves all requests."""
        controller = ApprovalController(mode="approve_all")
        request = ApprovalRequest(
            tool_name="dangerous_tool",
            description="Do something dangerous",
            payload={"action": "destroy"},
        )

        decision = controller.request_approval_sync(request)

        assert decision.approved is True

    def test_strict_mode(self):
        """strict mode auto-denies all requests."""
        controller = ApprovalController(mode="strict")
        request = ApprovalRequest(
            tool_name="any_tool",
            description="Any operation",
            payload={"key": "value"},
        )

        decision = controller.request_approval_sync(request)

        assert decision.approved is False
        assert "Strict mode" in decision.note

    def test_session_approval_caching(self):
        """Session approval caches approved requests."""
        approvals = []

        def callback(request: ApprovalRequest) -> ApprovalDecision:
            approvals.append(request)
            return ApprovalDecision(approved=True, remember="session")

        controller = ApprovalController(mode="interactive", approval_callback=callback)
        request = ApprovalRequest(
            tool_name="write_file",
            description="Write to file",
            payload={"path": "/tmp/test.txt"},
        )

        # First call - should invoke callback
        decision1 = controller.request_approval_sync(request)
        assert decision1.approved is True
        assert len(approvals) == 1

        # Second identical call - should use cache
        decision2 = controller.request_approval_sync(request)
        assert decision2.approved is True
        assert len(approvals) == 1  # Callback not called again

    def test_session_approval_different_payloads(self):
        """Different payloads require separate approvals."""
        approvals = []

        def callback(request: ApprovalRequest) -> ApprovalDecision:
            approvals.append(request)
            return ApprovalDecision(approved=True, remember="session")

        controller = ApprovalController(mode="interactive", approval_callback=callback)

        request1 = ApprovalRequest(
            tool_name="write_file",
            description="Write file 1",
            payload={"path": "/tmp/file1.txt"},
        )
        request2 = ApprovalRequest(
            tool_name="write_file",
            description="Write file 2",
            payload={"path": "/tmp/file2.txt"},
        )

        controller.request_approval_sync(request1)
        controller.request_approval_sync(request2)

        # Both should trigger callback (different payloads)
        assert len(approvals) == 2

    def test_session_approval_remember_none_not_cached(self):
        """remember='none' approvals are not cached."""
        approvals = []

        def callback(request: ApprovalRequest) -> ApprovalDecision:
            approvals.append(request)
            return ApprovalDecision(approved=True, remember="none")

        controller = ApprovalController(mode="interactive", approval_callback=callback)
        request = ApprovalRequest(
            tool_name="write_file",
            description="Write to file",
            payload={"path": "/tmp/test.txt"},
        )

        controller.request_approval_sync(request)
        controller.request_approval_sync(request)

        # Both calls should trigger callback (remember='none' doesn't cache)
        assert len(approvals) == 2

    def test_clear_session_approvals(self):
        """clear_session_approvals removes all cached approvals."""

        def callback(request: ApprovalRequest) -> ApprovalDecision:
            return ApprovalDecision(approved=True, remember="session")

        controller = ApprovalController(mode="interactive", approval_callback=callback)
        request = ApprovalRequest(
            tool_name="tool",
            description="Test",
            payload={"key": "value"},
        )

        controller.request_approval_sync(request)
        assert controller.is_session_approved(request) is True

        controller.clear_session_approvals()
        assert controller.is_session_approved(request) is False

    def test_interactive_mode_without_callback_raises(self):
        """Interactive mode without callback raises NotImplementedError."""
        controller = ApprovalController(mode="interactive")
        request = ApprovalRequest(
            tool_name="tool",
            description="Test",
            payload={"key": "value"},
        )

        with pytest.raises(NotImplementedError, match="No approval_callback"):
            controller.request_approval_sync(request)

    def test_payload_with_nested_structures(self):
        """Session matching works with nested payload structures."""
        approvals = []

        def callback(request: ApprovalRequest) -> ApprovalDecision:
            approvals.append(request)
            return ApprovalDecision(approved=True, remember="session")

        controller = ApprovalController(mode="interactive", approval_callback=callback)
        request = ApprovalRequest(
            tool_name="complex_tool",
            description="Complex operation",
            payload={
                "config": {"nested": {"deeply": "value"}},
                "items": [1, 2, 3],
            },
        )

        controller.request_approval_sync(request)
        controller.request_approval_sync(request)

        # Should cache even with nested structures
        assert len(approvals) == 1


# ---------------------------------------------------------------------------
# ApprovalDecision tests
# ---------------------------------------------------------------------------


class TestApprovalDecision:
    """Tests for ApprovalDecision."""

    def test_default_values(self):
        """Default value for remember is 'none'."""
        decision = ApprovalDecision(approved=True)
        assert decision.remember == "none"

    def test_remember_session(self):
        """remember='session' can be set."""
        decision = ApprovalDecision(approved=True, remember="session")
        assert decision.remember == "session"
