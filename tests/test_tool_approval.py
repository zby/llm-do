"""Tests for the tool_approval module.

This module tests the framework-agnostic approval types and utilities:
- @requires_approval decorator (Pattern 1)
- ApprovalController session approval matching
- simple_approval_request factory
- ApprovalToolset wrapper
"""
import pytest

from llm_do.tool_approval import (
    ApprovalContext,
    ApprovalController,
    ApprovalDecision,
    ApprovalRequest,
    requires_approval,
    simple_approval_request,
)


# ---------------------------------------------------------------------------
# @requires_approval decorator tests
# ---------------------------------------------------------------------------


class TestRequiresApprovalDecorator:
    """Tests for the @requires_approval decorator (Pattern 1)."""

    def test_basic_decorator_attaches_check_approval(self):
        """Decorator attaches check_approval to function."""

        @requires_approval()
        def my_tool(arg: str) -> str:
            return f"done: {arg}"

        # Function should have check_approval attribute
        assert hasattr(my_tool, "check_approval")

        # check_approval should return ApprovalRequest
        ctx = ApprovalContext(tool_name="my_tool", args={"arg": "test"})
        request = my_tool.check_approval(ctx)

        assert isinstance(request, ApprovalRequest)
        assert request.tool_name == "my_tool"
        assert request.payload == {"arg": "test"}

    def test_decorator_auto_generates_description(self):
        """Decorator auto-generates description from function name and args."""

        @requires_approval()
        def delete_file(path: str) -> str:
            return f"deleted: {path}"

        ctx = ApprovalContext(tool_name="delete_file", args={"path": "/tmp/test.txt"})
        request = delete_file.check_approval(ctx)

        assert "delete_file" in request.description
        assert "/tmp/test.txt" in request.description

    def test_decorator_custom_description_string(self):
        """Decorator accepts custom static description."""

        @requires_approval(description="Delete a file permanently")
        def delete_file(path: str) -> str:
            return f"deleted: {path}"

        ctx = ApprovalContext(tool_name="delete_file", args={"path": "/tmp/test.txt"})
        request = delete_file.check_approval(ctx)

        assert request.description == "Delete a file permanently"

    def test_decorator_custom_description_callable(self):
        """Decorator accepts callable for dynamic description."""

        @requires_approval(description=lambda args: f"Delete {args['path']}")
        def delete_file(path: str) -> str:
            return f"deleted: {path}"

        ctx = ApprovalContext(tool_name="delete_file", args={"path": "/tmp/test.txt"})
        request = delete_file.check_approval(ctx)

        assert request.description == "Delete /tmp/test.txt"

    def test_decorator_exclude_keys(self):
        """Decorator excludes specified keys from payload."""

        @requires_approval(exclude_keys={"content", "secret"})
        def write_file(path: str, content: str, secret: str = "") -> str:
            return f"written: {path}"

        ctx = ApprovalContext(
            tool_name="write_file",
            args={"path": "/tmp/test.txt", "content": "sensitive data", "secret": "key123"},
        )
        request = write_file.check_approval(ctx)

        # Only path should be in payload
        assert request.payload == {"path": "/tmp/test.txt"}
        assert "content" not in request.payload
        assert "secret" not in request.payload

    def test_decorator_custom_payload(self):
        """Decorator accepts custom payload generator."""

        @requires_approval(payload=lambda args: {"normalized_path": args["path"].lower()})
        def access_file(path: str) -> str:
            return f"accessed: {path}"

        ctx = ApprovalContext(tool_name="access_file", args={"path": "/TMP/Test.TXT"})
        request = access_file.check_approval(ctx)

        assert request.payload == {"normalized_path": "/tmp/test.txt"}

    def test_decorated_function_still_works(self):
        """Decorated function still executes normally."""

        @requires_approval()
        def add_numbers(a: int, b: int) -> int:
            return a + b

        # Function should still work
        result = add_numbers(2, 3)
        assert result == 5

    def test_decorator_preserves_function_metadata(self):
        """Decorator preserves function name and docstring."""

        @requires_approval()
        def my_documented_tool(x: int) -> int:
            """This is my tool's docstring."""
            return x * 2

        assert my_documented_tool.__name__ == "my_documented_tool"
        assert "docstring" in my_documented_tool.__doc__


# ---------------------------------------------------------------------------
# simple_approval_request factory tests
# ---------------------------------------------------------------------------


class TestSimpleApprovalRequest:
    """Tests for the simple_approval_request factory function."""

    def test_basic_request(self):
        """Factory creates basic approval request."""
        request = simple_approval_request("my_tool", {"arg1": "value1", "arg2": 42})

        assert request.tool_name == "my_tool"
        assert request.payload == {"arg1": "value1", "arg2": 42}
        assert "my_tool" in request.description

    def test_custom_description(self):
        """Factory accepts custom description."""
        request = simple_approval_request(
            "send_email",
            {"to": "user@example.com"},
            description="Send an email",
        )

        assert request.description == "Send an email"

    def test_exclude_keys(self):
        """Factory excludes specified keys from payload."""
        request = simple_approval_request(
            "write_file",
            {"path": "/tmp/file.txt", "content": "secret data"},
            exclude_keys={"content"},
        )

        assert request.payload == {"path": "/tmp/file.txt"}
        assert "content" not in request.payload


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
            return ApprovalDecision(approved=True, scope="session")

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
            return ApprovalDecision(approved=True, scope="session")

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

    def test_session_approval_once_scope_not_cached(self):
        """scope='once' approvals are not cached."""
        approvals = []

        def callback(request: ApprovalRequest) -> ApprovalDecision:
            approvals.append(request)
            return ApprovalDecision(approved=True, scope="once")

        controller = ApprovalController(mode="interactive", approval_callback=callback)
        request = ApprovalRequest(
            tool_name="write_file",
            description="Write to file",
            payload={"path": "/tmp/test.txt"},
        )

        controller.request_approval_sync(request)
        controller.request_approval_sync(request)

        # Both calls should trigger callback (once scope doesn't cache)
        assert len(approvals) == 2

    def test_clear_session_approvals(self):
        """clear_session_approvals removes all cached approvals."""

        def callback(request: ApprovalRequest) -> ApprovalDecision:
            return ApprovalDecision(approved=True, scope="session")

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
            return ApprovalDecision(approved=True, scope="session")

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
