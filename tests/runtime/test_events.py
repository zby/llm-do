"""Tests for event emission in runtime.

These tests verify that events are properly emitted during execution
via the on_event callback mechanism.
"""
import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import InvocableRegistry, Worker, WorkerRuntime
from llm_do.ui.events import (
    TextResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
    UIEvent,
)


class TestContextEventCallback:
    """Tests for WorkerRuntime event callback wiring."""

    def test_child_context_inherits_on_event(self):
        """Test that child contexts inherit on_event callback."""
        events = []
        def callback(e):
            return events.append(e)
        ctx = WorkerRuntime(
            toolsets=[],
            model="test-model",
            on_event=callback,
        )
        child = ctx.spawn_child()
        assert child.on_event is callback

    def test_child_context_inherits_verbosity(self):
        """Test that child contexts inherit verbosity."""
        ctx = WorkerRuntime(
            toolsets=[],
            model="test-model",
            verbosity=2,
        )
        child = ctx.spawn_child()
        assert child.verbosity == 2

    @pytest.mark.anyio
    async def test_context_call_emits_events(self):
        """Test that ctx.call() emits ToolCallEvent and ToolResultEvent."""
        events: list[UIEvent] = []

        # Create a toolset with a simple tool
        toolset = FunctionToolset()

        @toolset.tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        ctx = WorkerRuntime(
            toolsets=[toolset],
            model="test-model",
            on_event=lambda e: events.append(e),
        )

        result = await ctx.call("greet", {"name": "World"})
        assert result == "Hello, World!"

        # Should have ToolCallEvent and ToolResultEvent
        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        assert len(tool_calls) == 1, f"Expected 1 ToolCallEvent, got: {events}"
        assert len(tool_results) == 1, f"Expected 1 ToolResultEvent, got: {events}"

        # Verify tool call event content
        call_event = tool_calls[0]
        assert call_event.tool_name == "greet"
        assert call_event.worker == "code_entry"
        assert call_event.args == {"name": "World"}

        # Verify tool result event content
        result_event = tool_results[0]
        assert result_event.tool_name == "greet"
        assert result_event.tool_call_id == call_event.tool_call_id
        assert result_event.content == "Hello, World!"


class TestWorkerToolEvents:
    """Tests for ToolCallEvent/ToolResultEvent emission from Worker."""

    @pytest.mark.anyio
    async def test_worker_emits_tool_call_event(self):
        """Test that Worker emits ToolCallEvent when tools are called."""
        events: list[UIEvent] = []

        # Create a toolset with a simple tool
        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        # Create worker with the toolset
        worker = Worker(
            name="calculator",
            instructions="You are a calculator. Use add tool.",
            model=TestModel(call_tools=["add"]),
            toolsets=[toolset],
        )

        ctx = WorkerRuntime.from_entry(
            worker,
            on_event=lambda e: events.append(e),
        )

        await ctx.run(worker, {"input": "Add 3 and 4"})

        # Should have ToolCallEvent and ToolResultEvent
        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        assert len(tool_calls) >= 1, f"Expected ToolCallEvent, got events: {events}"
        assert len(tool_results) >= 1, f"Expected ToolResultEvent, got events: {events}"

        # Verify tool call event content
        call_event = tool_calls[0]
        assert call_event.tool_name == "add"
        assert call_event.worker == "calculator"
        assert call_event.tool_call_id is not None

        # Verify tool result event content
        result_event = tool_results[0]
        assert result_event.tool_name == "add"
        assert result_event.tool_call_id == call_event.tool_call_id

    @pytest.mark.anyio
    async def test_worker_emits_events_for_multiple_tool_calls(self):
        """Test that Worker emits events for multiple tool calls."""
        events: list[UIEvent] = []

        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        worker = Worker(
            name="calculator",
            instructions="You are a calculator.",
            model=TestModel(call_tools=["add", "multiply"]),
            toolsets=[toolset],
        )

        ctx = WorkerRuntime.from_entry(
            worker,
            on_event=lambda e: events.append(e),
        )

        await ctx.run(worker, {"input": "Calculate"})

        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        # Should have events for both tools
        assert len(tool_calls) >= 2
        assert len(tool_results) >= 2

        tool_names = {e.tool_name for e in tool_calls}
        assert "add" in tool_names
        assert "multiply" in tool_names

    @pytest.mark.anyio
    async def test_tool_call_ids_correlate(self):
        """Test that tool_call_id correlates ToolCallEvent with ToolResultEvent."""
        events: list[UIEvent] = []

        toolset = FunctionToolset()

        @toolset.tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        worker = Worker(
            name="greeter",
            instructions="Greet the user.",
            model=TestModel(call_tools=["greet"]),
            toolsets=[toolset],
        )

        ctx = WorkerRuntime.from_entry(
            worker,
            on_event=lambda e: events.append(e),
        )

        await ctx.run(worker, {"input": "Greet Alice"})

        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        assert len(tool_calls) >= 1
        assert len(tool_results) >= 1

        # Find matching pair by tool_call_id
        call_ids = {e.tool_call_id for e in tool_calls}
        result_ids = {e.tool_call_id for e in tool_results}

        # At least one call_id should match
        assert call_ids & result_ids, "tool_call_id should correlate call with result"

    @pytest.mark.anyio
    async def test_no_events_when_callback_is_none(self):
        """Test that no crash occurs when on_event is None."""
        toolset = FunctionToolset()

        @toolset.tool
        def echo(msg: str) -> str:
            return msg

        worker = Worker(
            name="echo",
            instructions="Echo the input.",
            model=TestModel(call_tools=["echo"]),
            toolsets=[toolset],
        )

        # No on_event callback
        ctx = WorkerRuntime.from_entry(worker)
        assert ctx.on_event is None

        # Should not crash
        result = await ctx.run(worker, {"input": "Hello"})
        assert result is not None


class TestWorkerStreamingEvents:
    """Tests for TextResponseEvent emission during streaming."""

    @pytest.mark.anyio
    async def test_streaming_emits_text_response_events(self):
        """Test that streaming mode emits TextResponseEvent deltas."""
        events: list[UIEvent] = []

        worker = Worker(
            name="assistant",
            instructions="Respond to the user.",
            model=TestModel(custom_output_text="Hello there!"),
            toolsets=[],
        )

        ctx = WorkerRuntime.from_entry(
            worker,
            on_event=lambda e: events.append(e),
            verbosity=2,  # Enable streaming
        )

        await ctx.run(worker, {"input": "Hi"})

        text_events = [e for e in events if isinstance(e, TextResponseEvent)]

        # Should have at least one text response event
        assert len(text_events) >= 1, f"Expected TextResponseEvent, got: {events}"

        # Check that we got delta events
        delta_events = [e for e in text_events if e.is_delta]
        assert len(delta_events) >= 1, "Expected delta text events during streaming"

        # Streaming should still emit a final complete response
        complete_events = [e for e in text_events if e.is_complete and not e.is_delta]
        assert len(complete_events) >= 1, "Expected final complete text response after streaming"

    @pytest.mark.anyio
    async def test_no_streaming_without_verbosity(self):
        """Test that verbosity < 2 doesn't stream (still emits tool events)."""
        events: list[UIEvent] = []

        worker = Worker(
            name="assistant",
            instructions="Respond to the user.",
            model=TestModel(custom_output_text="Hello!"),
            toolsets=[],
        )

        ctx = WorkerRuntime.from_entry(
            worker,
            on_event=lambda e: events.append(e),
            verbosity=1,  # Not streaming level
        )

        await ctx.run(worker, {"input": "Hi"})

        # Should NOT have streaming text events (deltas)
        text_events = [e for e in events if isinstance(e, TextResponseEvent) and e.is_delta]
        assert len(text_events) == 0, "Should not stream text at verbosity=1"


class TestCLIEventIntegration:
    """Tests for CLI event integration with display backends."""

    @pytest.mark.anyio
    async def test_run_with_on_event(self):
        """Test that run() accepts and uses on_event callback."""
        from llm_do.cli.main import run

        events: list[UIEvent] = []

        worker = Worker(
            name="main",
            instructions="Test worker",
            model=TestModel(custom_output_text="Hello!"),
            toolsets=[],
        )

        result, ctx = await run(
            files=[],
            prompt="Hi there",
            on_event=lambda e: events.append(e),
            verbosity=1,
            registry=InvocableRegistry(entries={"main": worker}),
        )

        assert result is not None
        assert ctx.on_event is not None

    @pytest.mark.anyio
    async def test_run_with_tools_emits_events(self):
        """Test that run() with tools emits ToolCallEvent/ToolResultEvent."""
        from llm_do.cli.main import run

        events: list[UIEvent] = []

        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            return a + b

        worker = Worker(
            name="main",
            instructions="Test worker",
            model=TestModel(
                call_tools=["add"],
                custom_output_text="The sum is 7.",
            ),
            toolsets=[toolset],
        )

        result, ctx = await run(
            files=[],
            prompt="Add 3 and 4",
            on_event=lambda e: events.append(e),
            verbosity=1,
            approve_all=True,
            registry=InvocableRegistry(entries={"main": worker}),
        )

        # Should have tool events
        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        assert len(tool_calls) >= 1, f"Expected ToolCallEvent, got: {events}"
        assert len(tool_results) >= 1, f"Expected ToolResultEvent, got: {events}"
