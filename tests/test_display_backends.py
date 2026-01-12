"""Tests for display backends (headless, JSON, etc.)."""
import io

from llm_do.ui.display import HeadlessDisplayBackend, JsonDisplayBackend
from llm_do.ui.events import (
    DeferredToolEvent,
    InitialRequestEvent,
    StatusEvent,
    TextResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from llm_do.ui.parser import parse_event


class TestHeadlessDisplayBackend:
    """Tests for HeadlessDisplayBackend."""

    def test_handles_initial_request_event(self):
        """Backend shows 'Starting...' for initial_request events."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        event = InitialRequestEvent(
            worker="test_worker",
            user_input="hello",
        )
        backend.display(event)
        output = stream.getvalue()
        assert "test_worker" in output
        assert "hello" in output

    def test_handles_status_event(self):
        """Backend formats status events with phase/state/model."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        event = StatusEvent(
            worker="analyzer",
            phase="processing",
            state="running",
            model="claude-haiku",
        )
        backend.display(event)
        output = stream.getvalue()
        assert "processing" in output
        assert "running" in output
        assert "claude-haiku" in output

    def test_handles_text_response_event(self):
        """Backend shows model response text."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        event = TextResponseEvent(
            worker="assistant",
            content="Hello, this is the response.",
            is_complete=True,
        )
        backend.display(event)

        output = stream.getvalue()
        assert "Hello, this is the response." in output

    def test_streaming_delta_does_not_append_newline(self):
        """Backend writes streaming deltas inline without a newline."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream, verbosity=2)

        event = TextResponseEvent(
            worker="assistant",
            content="Hello",
            is_complete=False,
            is_delta=True,
        )
        backend.display(event)

        assert stream.getvalue() == "Hello"

    def test_handles_tool_call_event(self):
        """Backend shows tool calls with name and args."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        event = ToolCallEvent(
            worker="main",
            tool_name="read_file",
            args={"path": "/tmp/test.txt"},
            tool_call_id="call_123",
        )
        backend.display(event)

        output = stream.getvalue()
        assert "read_file" in output
        assert "/tmp/test.txt" in output

    def test_handles_tool_result_event(self):
        """Backend shows tool results."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        event = ToolResultEvent(
            worker="main",
            tool_name="read_file",
            content="File contents here",
            tool_call_id="call_123",
        )
        backend.display(event)

        output = stream.getvalue()
        assert "File contents here" in output

    def test_truncates_long_tool_args(self):
        """Backend truncates very long tool arguments."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        long_content = "x" * 500
        event = ToolCallEvent(
            worker="main",
            tool_name="write_file",
            args={"content": long_content},
            args_json=str({"content": long_content}),
            tool_call_id="call_123",
        )
        backend.display(event)

        output = stream.getvalue()
        # Should not contain the full 500 chars (limit is 400)
        assert long_content not in output

    def test_truncates_long_tool_results(self):
        """Backend truncates very long tool results."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        long_content = "line\n" * 100  # 100 lines
        event = ToolResultEvent(
            worker="main",
            tool_name="read_file",
            content=long_content,
            tool_call_id="call_123",
        )
        backend.display(event)

        output = stream.getvalue()
        # Should not contain the full output
        assert long_content not in output

    def test_handles_deferred_tool_event(self):
        """Backend shows deferred tool status."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        event = DeferredToolEvent(
            worker="main",
            tool_name="slow_operation",
            status="pending",
        )
        backend.display(event)
        output = stream.getvalue()
        assert "slow_operation" in output
        assert "pending" in output

    def test_handles_empty_status_event(self):
        """Backend handles empty status event gracefully."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        event = StatusEvent(worker="main", phase="", state="")
        backend.display(event)
        # Should not crash, output should be minimal (None returned from render)
        assert stream.getvalue() == ""

    def test_multiline_response(self):
        """Backend properly indents multiline responses."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        event = TextResponseEvent(
            worker="main",
            content="Line 1\nLine 2\nLine 3",
            is_complete=True,
        )
        backend.display(event)

        output = stream.getvalue()
        assert "Line 1" in output
        assert "Line 2" in output
        assert "Line 3" in output


class TestJsonDisplayBackend:
    """Tests for JsonDisplayBackend."""

    def test_writes_jsonl_to_stream(self):
        """Backend writes JSONL records to stream."""
        import json

        stream = io.StringIO()
        backend = JsonDisplayBackend(stream=stream)
        event = StatusEvent(worker="test", phase="running", state="active")
        backend.display(event)

        output = stream.getvalue().strip()
        record = json.loads(output)
        assert record["type"] == "status"
        assert record["worker"] == "test"
        assert record["phase"] == "running"

    def test_writes_tool_call_as_jsonl(self):
        """Backend writes tool call events as JSONL."""
        import json

        stream = io.StringIO()
        backend = JsonDisplayBackend(stream=stream)
        event = ToolCallEvent(
            worker="main",
            tool_name="test_tool",
            args={"key": "value"},
        )
        backend.display(event)

        output = stream.getvalue().strip()
        record = json.loads(output)
        assert record["type"] == "tool_call"
        assert record["tool_name"] == "test_tool"
        assert record["args"]["key"] == "value"

    def test_writes_deferred_tool_as_jsonl(self):
        """Backend writes deferred tool events as JSONL."""
        import json

        stream = io.StringIO()
        backend = JsonDisplayBackend(stream=stream)
        event = DeferredToolEvent(
            worker="main",
            tool_name="test",
            status="done",
        )
        backend.display(event)

        output = stream.getvalue().strip()
        record = json.loads(output)
        assert record["type"] == "deferred_tool"
        assert record["tool_name"] == "test"
        assert record["status"] == "done"


class TestParseEvent:
    """Tests for the parse_event function."""

    def test_parse_initial_request(self):
        """Parser converts initial_request payload to InitialRequestEvent."""
        payload = {
            "worker": "test",
            "initial_request": {
                "instructions": "Do something",
                "user_input": "Hello",
                "attachments": [],
            },
        }
        event = parse_event(payload)
        assert isinstance(event, InitialRequestEvent)
        assert event.worker == "test"
        assert event.instructions == "Do something"
        assert event.user_input == "Hello"

    def test_parse_status_dict(self):
        """Parser converts status dict to StatusEvent."""
        payload = {
            "worker": "main",
            "status": {
                "phase": "processing",
                "state": "running",
                "model": "claude",
            },
        }
        event = parse_event(payload)
        assert isinstance(event, StatusEvent)
        assert event.phase == "processing"
        assert event.state == "running"
        assert event.model == "claude"

    def test_parse_status_string(self):
        """Parser converts status string to StatusEvent."""
        payload = {
            "worker": "main",
            "status": "Waiting",
        }
        event = parse_event(payload)
        assert isinstance(event, StatusEvent)
        assert event.phase == "Waiting"

    def test_parse_text_part_event(self):
        """Parser converts PartEndEvent with TextPart to TextResponseEvent."""
        from pydantic_ai.messages import PartEndEvent, TextPart

        text_part = TextPart(content="Hello response")
        raw_event = PartEndEvent(index=0, part=text_part)

        payload = {
            "worker": "assistant",
            "event": raw_event,
        }
        event = parse_event(payload)
        assert isinstance(event, TextResponseEvent)
        assert event.content == "Hello response"
        assert event.is_complete is True

    def test_parse_tool_call_event(self):
        """Parser converts FunctionToolCallEvent to ToolCallEvent."""
        from pydantic_ai.messages import FunctionToolCallEvent, ToolCallPart

        tool_part = ToolCallPart(
            tool_name="read_file",
            args={"path": "/tmp/test"},
            tool_call_id="call_123",
        )
        raw_event = FunctionToolCallEvent(part=tool_part)

        payload = {
            "worker": "main",
            "event": raw_event,
        }
        event = parse_event(payload)
        assert isinstance(event, ToolCallEvent)
        assert event.tool_name == "read_file"
        assert event.args == {"path": "/tmp/test"}

    def test_parse_tool_result_event(self):
        """Parser converts FunctionToolResultEvent to ToolResultEvent."""
        from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart

        result_part = ToolReturnPart(
            tool_name="read_file",
            content="File contents",
            tool_call_id="call_123",
        )
        raw_event = FunctionToolResultEvent(result=result_part)

        payload = {
            "worker": "main",
            "event": raw_event,
        }
        event = parse_event(payload)
        assert isinstance(event, ToolResultEvent)
        assert event.tool_name == "read_file"
        assert event.content == "File contents"

    def test_parse_unknown_payload(self):
        """Parser returns StatusEvent for unknown payloads."""
        payload = {"worker": "main"}
        event = parse_event(payload)
        assert isinstance(event, StatusEvent)
        assert event.worker == "main"
