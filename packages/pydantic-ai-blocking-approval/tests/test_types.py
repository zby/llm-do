"""Tests for approval types."""
import pytest

from pydantic_ai_blocking_approval import (
    ApprovalDecision,
    ApprovalPresentation,
    ApprovalRequest,
)


class TestApprovalPresentation:
    """Tests for ApprovalPresentation."""

    def test_basic_presentation(self):
        """Create a basic text presentation."""
        presentation = ApprovalPresentation(
            type="text",
            content="Simple message",
        )
        assert presentation.type == "text"
        assert presentation.content == "Simple message"
        assert presentation.language is None
        assert presentation.metadata == {}

    def test_presentation_with_language(self):
        """Create a presentation with syntax highlighting hint."""
        presentation = ApprovalPresentation(
            type="file_content",
            content="def hello(): pass",
            language="python",
        )
        assert presentation.language == "python"

    def test_presentation_with_metadata(self):
        """Create a presentation with metadata."""
        presentation = ApprovalPresentation(
            type="diff",
            content="- old\n+ new",
            metadata={"file": "test.py", "lines": 10},
        )
        assert presentation.metadata["file"] == "test.py"


class TestApprovalRequest:
    """Tests for ApprovalRequest."""

    def test_basic_request(self):
        """Create a basic approval request."""
        request = ApprovalRequest(
            tool_name="write_file",
            description="Write to /tmp/test.txt",
            payload={"path": "/tmp/test.txt"},
        )
        assert request.tool_name == "write_file"
        assert request.description == "Write to /tmp/test.txt"
        assert request.payload == {"path": "/tmp/test.txt"}
        assert request.presentation is None

    def test_request_with_presentation(self):
        """Create a request with rich presentation."""
        presentation = ApprovalPresentation(type="text", content="Details")
        request = ApprovalRequest(
            tool_name="shell",
            description="Run command",
            payload={"command": "ls"},
            presentation=presentation,
        )
        assert request.presentation is not None
        assert request.presentation.type == "text"


class TestApprovalDecision:
    """Tests for ApprovalDecision."""

    def test_approved_once(self):
        """Create an approved-once decision."""
        decision = ApprovalDecision(approved=True)
        assert decision.approved is True
        assert decision.remember == "none"
        assert decision.note is None

    def test_approved_session(self):
        """Create an approved-for-session decision."""
        decision = ApprovalDecision(approved=True, remember="session")
        assert decision.approved is True
        assert decision.remember == "session"

    def test_denied_with_note(self):
        """Create a denied decision with a note."""
        decision = ApprovalDecision(
            approved=False,
            note="Not safe to execute",
        )
        assert decision.approved is False
        assert decision.note == "Not safe to execute"
