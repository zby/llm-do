"""Tests for ApprovalController."""
import pytest

from pydantic_ai_blocking_approval import (
    ApprovalController,
    ApprovalDecision,
    ApprovalRequest,
)


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

    def test_approval_callback_property_approve_all(self):
        """approval_callback property returns auto-approve for approve_all mode."""
        controller = ApprovalController(mode="approve_all")
        callback = controller.approval_callback

        request = ApprovalRequest(
            tool_name="tool",
            description="Test",
            payload={},
        )
        decision = callback(request)

        assert decision.approved is True

    def test_approval_callback_property_strict(self):
        """approval_callback property returns auto-deny for strict mode."""
        controller = ApprovalController(mode="strict")
        callback = controller.approval_callback

        request = ApprovalRequest(
            tool_name="tool",
            description="Test",
            payload={},
        )
        decision = callback(request)

        assert decision.approved is False

    def test_approval_callback_property_interactive_no_callback_raises(self):
        """approval_callback property raises for interactive mode without callback."""
        controller = ApprovalController(mode="interactive")

        with pytest.raises(RuntimeError, match="No approval_callback set"):
            _ = controller.approval_callback
