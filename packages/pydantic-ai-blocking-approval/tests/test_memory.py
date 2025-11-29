"""Tests for ApprovalMemory."""
import pytest

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalMemory


class TestApprovalMemory:
    """Tests for ApprovalMemory session caching."""

    def test_lookup_empty(self):
        """Lookup on empty memory returns None."""
        memory = ApprovalMemory()
        result = memory.lookup("tool", {"key": "value"})
        assert result is None

    def test_store_and_lookup(self):
        """Store and retrieve a decision."""
        memory = ApprovalMemory()
        decision = ApprovalDecision(approved=True, remember="session")

        memory.store("write_file", {"path": "/tmp/test.txt"}, decision)

        result = memory.lookup("write_file", {"path": "/tmp/test.txt"})
        assert result is not None
        assert result.approved is True

    def test_store_remember_none_not_cached(self):
        """Decisions with remember='none' are not cached."""
        memory = ApprovalMemory()
        decision = ApprovalDecision(approved=True, remember="none")

        memory.store("tool", {"key": "value"}, decision)

        result = memory.lookup("tool", {"key": "value"})
        assert result is None

    def test_different_payloads_different_keys(self):
        """Different payloads are stored separately."""
        memory = ApprovalMemory()
        decision1 = ApprovalDecision(approved=True, remember="session")
        decision2 = ApprovalDecision(approved=False, remember="session", note="denied")

        memory.store("write_file", {"path": "/tmp/file1.txt"}, decision1)
        memory.store("write_file", {"path": "/tmp/file2.txt"}, decision2)

        result1 = memory.lookup("write_file", {"path": "/tmp/file1.txt"})
        result2 = memory.lookup("write_file", {"path": "/tmp/file2.txt"})

        assert result1.approved is True
        assert result2.approved is False

    def test_different_tools_different_keys(self):
        """Different tool names are stored separately."""
        memory = ApprovalMemory()
        decision1 = ApprovalDecision(approved=True, remember="session")
        decision2 = ApprovalDecision(approved=False, remember="session")

        memory.store("read_file", {"path": "/tmp/test.txt"}, decision1)
        memory.store("write_file", {"path": "/tmp/test.txt"}, decision2)

        result1 = memory.lookup("read_file", {"path": "/tmp/test.txt"})
        result2 = memory.lookup("write_file", {"path": "/tmp/test.txt"})

        assert result1.approved is True
        assert result2.approved is False

    def test_clear(self):
        """Clear removes all cached decisions."""
        memory = ApprovalMemory()
        decision = ApprovalDecision(approved=True, remember="session")

        memory.store("tool1", {"key": "value1"}, decision)
        memory.store("tool2", {"key": "value2"}, decision)

        memory.clear()

        assert memory.lookup("tool1", {"key": "value1"}) is None
        assert memory.lookup("tool2", {"key": "value2"}) is None

    def test_payload_order_independent(self):
        """Payload key order doesn't affect matching."""
        memory = ApprovalMemory()
        decision = ApprovalDecision(approved=True, remember="session")

        # Store with one key order
        memory.store("tool", {"a": 1, "b": 2}, decision)

        # Lookup with different key order
        result = memory.lookup("tool", {"b": 2, "a": 1})
        assert result is not None
        assert result.approved is True
