"""Tests for display backends (headless, JSON, etc.)."""
import io
from unittest.mock import MagicMock

import pytest

from llm_do.ui.display import HeadlessDisplayBackend, JsonDisplayBackend, CLIEvent


class TestHeadlessDisplayBackend:
    """Tests for HeadlessDisplayBackend."""

    def test_writes_to_stream(self):
        """Backend writes to provided stream."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        backend._write("test message")
        assert "test message\n" in stream.getvalue()

    def test_handles_string_payload(self):
        """Backend handles string payloads (errors, status)."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        backend.display_runtime_event("Error occurred")
        assert "Error occurred" in stream.getvalue()

    def test_handles_initial_request_event(self):
        """Backend shows 'Starting...' for initial_request events."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        backend.display_runtime_event({
            "worker": "test_worker",
            "initial_request": {"input": "hello"},
        })
        assert "[test_worker] Starting..." in stream.getvalue()

    def test_handles_status_dict_event(self):
        """Backend formats status dict events with phase/state/model."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        backend.display_runtime_event({
            "worker": "analyzer",
            "status": {
                "phase": "processing",
                "state": "running",
                "model": "claude-haiku",
            },
        })
        output = stream.getvalue()
        assert "[analyzer]" in output
        assert "processing" in output
        assert "running" in output
        assert "claude-haiku" in output

    def test_handles_status_string_event(self):
        """Backend handles simple string status."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        backend.display_runtime_event({
            "worker": "main",
            "status": "Waiting for approval",
        })
        assert "[main] Waiting for approval" in stream.getvalue()

    def test_handles_text_part_event(self):
        """Backend shows model response text."""
        from pydantic_ai.messages import PartEndEvent, TextPart

        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        text_part = TextPart(content="Hello, this is the response.")
        event = PartEndEvent(index=0, part=text_part)

        backend.display_runtime_event({
            "worker": "assistant",
            "event": event,
        })

        output = stream.getvalue()
        assert "[assistant] Response:" in output
        assert "Hello, this is the response." in output

    def test_handles_tool_call_event(self):
        """Backend shows tool calls with name and args."""
        from pydantic_ai.messages import FunctionToolCallEvent, ToolCallPart

        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        tool_part = ToolCallPart(
            tool_name="read_file",
            args={"path": "/tmp/test.txt"},
            tool_call_id="call_123",
        )
        event = FunctionToolCallEvent(part=tool_part)

        backend.display_runtime_event({
            "worker": "main",
            "event": event,
        })

        output = stream.getvalue()
        assert "[main] Tool call: read_file" in output
        assert "path" in output
        assert "/tmp/test.txt" in output

    def test_handles_tool_result_event(self):
        """Backend shows tool results."""
        from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart

        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        result_part = ToolReturnPart(
            tool_name="read_file",
            content="File contents here",
            tool_call_id="call_123",
        )
        event = FunctionToolResultEvent(result=result_part)

        backend.display_runtime_event({
            "worker": "main",
            "event": event,
        })

        output = stream.getvalue()
        assert "[main] Tool result: read_file" in output
        assert "File contents here" in output

    def test_truncates_long_tool_args(self):
        """Backend truncates very long tool arguments."""
        from pydantic_ai.messages import FunctionToolCallEvent, ToolCallPart

        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        long_content = "x" * 300
        tool_part = ToolCallPart(
            tool_name="write_file",
            args={"content": long_content},
            tool_call_id="call_123",
        )
        event = FunctionToolCallEvent(part=tool_part)

        backend.display_runtime_event({
            "worker": "main",
            "event": event,
        })

        output = stream.getvalue()
        assert "..." in output
        # Should not contain the full 300 chars
        assert long_content not in output

    def test_truncates_long_tool_results(self):
        """Backend truncates very long tool results."""
        from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart

        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        long_content = "line\n" * 100  # 100 lines
        result_part = ToolReturnPart(
            tool_name="read_file",
            content=long_content,
            tool_call_id="call_123",
        )
        event = FunctionToolResultEvent(result=result_part)

        backend.display_runtime_event({
            "worker": "main",
            "event": event,
        })

        output = stream.getvalue()
        # Should have truncation indicator
        assert "more lines" in output

    def test_handles_deferred_tool(self):
        """Backend shows deferred tool status."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        backend.display_deferred_tool({
            "tool_name": "slow_operation",
            "status": "pending",
        })
        assert "Deferred tool 'slow_operation': pending" in stream.getvalue()

    def test_ignores_none_event(self):
        """Backend handles None event payload gracefully."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        backend.display_runtime_event({
            "worker": "main",
            "event": None,
        })
        # Should not crash, output should be minimal
        assert stream.getvalue() == ""

    def test_multiline_response(self):
        """Backend properly indents multiline responses."""
        from pydantic_ai.messages import PartEndEvent, TextPart

        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        text_part = TextPart(content="Line 1\nLine 2\nLine 3")
        event = PartEndEvent(index=0, part=text_part)

        backend.display_runtime_event({
            "worker": "main",
            "event": event,
        })

        output = stream.getvalue()
        assert "  Line 1" in output
        assert "  Line 2" in output
        assert "  Line 3" in output


class TestJsonDisplayBackend:
    """Tests for JsonDisplayBackend."""

    def test_writes_jsonl_to_stream(self):
        """Backend writes JSONL records to stream."""
        import json

        stream = io.StringIO()
        backend = JsonDisplayBackend(stream=stream)
        backend.display_runtime_event({"test": "value"})

        output = stream.getvalue().strip()
        record = json.loads(output)
        assert record["kind"] == "runtime_event"
        assert record["payload"]["test"] == "value"

    def test_writes_deferred_tool_as_jsonl(self):
        """Backend writes deferred tool events as JSONL."""
        import json

        stream = io.StringIO()
        backend = JsonDisplayBackend(stream=stream)
        backend.display_deferred_tool({"tool_name": "test", "status": "done"})

        output = stream.getvalue().strip()
        record = json.loads(output)
        assert record["kind"] == "deferred_tool"
        assert record["payload"]["tool_name"] == "test"

    def test_handles_pydantic_models(self):
        """Backend serializes pydantic models via model_dump."""
        import json
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            value: int

        stream = io.StringIO()
        backend = JsonDisplayBackend(stream=stream)
        backend.display_runtime_event(TestModel(name="test", value=42))

        output = stream.getvalue().strip()
        record = json.loads(output)
        assert record["payload"]["name"] == "test"
        assert record["payload"]["value"] == 42


class TestCLIEvent:
    """Tests for CLIEvent dataclass."""

    def test_cli_event_creation(self):
        """CLIEvent can be created with kind and payload."""
        event = CLIEvent(kind="runtime_event", payload={"test": True})
        assert event.kind == "runtime_event"
        assert event.payload == {"test": True}

    def test_cli_event_kinds(self):
        """CLIEvent supports all documented kinds."""
        for kind in ["runtime_event", "deferred_tool", "approval_request"]:
            event = CLIEvent(kind=kind, payload={})
            assert event.kind == kind
