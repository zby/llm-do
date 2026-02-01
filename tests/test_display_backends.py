"""Tests for display backends (headless, etc.)."""
import io

from llm_do.runtime.events import RuntimeEvent
from llm_do.runtime.events import UserMessageEvent as RuntimeUserMessageEvent
from llm_do.ui.adapter import adapt_event
from llm_do.ui.display import HeadlessDisplayBackend
from llm_do.ui.events import (
    DeferredToolEvent,
    InitialRequestEvent,
    StatusEvent,
    TextResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)


class TestHeadlessDisplayBackend:
    """Tests for HeadlessDisplayBackend."""

    def test_handles_initial_request_event(self):
        """Backend shows 'Starting...' for initial_request events."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        event = InitialRequestEvent(
            agent="test_agent",
            user_input="hello",
        )
        backend.display(event)
        output = stream.getvalue()
        assert "test_agent" in output
        assert "hello" in output

    def test_handles_status_event(self):
        """Backend formats status events with phase/state/model."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)
        event = StatusEvent(
            agent="analyzer",
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
            agent="assistant",
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
            agent="assistant",
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
            agent="main",
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
            agent="main",
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
            agent="main",
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
            agent="main",
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
            agent="main",
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
        event = StatusEvent(agent="main", phase="", state="")
        backend.display(event)
        # Should not crash, output should be minimal (None returned from render)
        assert stream.getvalue() == ""

    def test_multiline_response(self):
        """Backend properly indents multiline responses."""
        stream = io.StringIO()
        backend = HeadlessDisplayBackend(stream=stream)

        event = TextResponseEvent(
            agent="main",
            content="Line 1\nLine 2\nLine 3",
            is_complete=True,
        )
        backend.display(event)

        output = stream.getvalue()
        assert "Line 1" in output
        assert "Line 2" in output
        assert "Line 3" in output


class TestAdaptEvent:
    """Tests for the runtime -> UI event adapter."""

    def test_parse_user_message_event(self):
        """Adapter converts user message system events to UI events."""
        runtime_event = RuntimeEvent(
            agent="main",
            depth=0,
            event=RuntimeUserMessageEvent(content="Hello"),
        )
        event = adapt_event(runtime_event)
        assert isinstance(event, UserMessageEvent)
        assert event.agent == "main"
        assert event.content == "Hello"

    def test_parse_text_part_event(self):
        """Adapter converts PartEndEvent with TextPart to TextResponseEvent."""
        from pydantic_ai.messages import PartEndEvent, TextPart

        text_part = TextPart(content="Hello response")
        raw_event = PartEndEvent(index=0, part=text_part)

        runtime_event = RuntimeEvent(agent="assistant", depth=0, event=raw_event)
        event = adapt_event(runtime_event)
        assert isinstance(event, TextResponseEvent)
        assert event.content == "Hello response"
        assert event.is_complete is True

    def test_parse_tool_call_event(self):
        """Adapter converts FunctionToolCallEvent to ToolCallEvent."""
        from pydantic_ai.messages import FunctionToolCallEvent, ToolCallPart

        tool_part = ToolCallPart(
            tool_name="read_file",
            args={"path": "/tmp/test"},
            tool_call_id="call_123",
        )
        raw_event = FunctionToolCallEvent(part=tool_part)

        runtime_event = RuntimeEvent(agent="main", depth=0, event=raw_event)
        event = adapt_event(runtime_event)
        assert isinstance(event, ToolCallEvent)
        assert event.tool_name == "read_file"
        assert event.args == {"path": "/tmp/test"}

    def test_parse_tool_result_event(self):
        """Adapter converts FunctionToolResultEvent to ToolResultEvent."""
        from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart

        result_part = ToolReturnPart(
            tool_name="read_file",
            content="File contents",
            tool_call_id="call_123",
        )
        raw_event = FunctionToolResultEvent(result=result_part)

        runtime_event = RuntimeEvent(agent="main", depth=0, event=raw_event)
        event = adapt_event(runtime_event)
        assert isinstance(event, ToolResultEvent)
        assert event.tool_name == "read_file"
        assert event.content == "File contents"

    def test_parse_unknown_payload(self):
        """Adapter ignores events it doesn't map."""
        from pydantic_ai.messages import PartStartEvent, ToolCallPart

        tool_part = ToolCallPart(
            tool_name="read_file",
            args={"path": "/tmp/test"},
            tool_call_id="call_123",
        )
        raw_event = PartStartEvent(index=0, part=tool_part)
        runtime_event = RuntimeEvent(agent="main", depth=0, event=raw_event)
        assert adapt_event(runtime_event) is None
