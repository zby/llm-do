"""Tests for event emission in ctx_runtime.

These tests verify that events are properly emitted during execution
via the on_event callback mechanism.
"""
import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from llm_do.ctx_runtime import Context, WorkerEntry
from llm_do.ui.events import (
    UIEvent,
    ToolCallEvent,
    ToolResultEvent,
    TextResponseEvent,
)


class TestContextEventCallback:
    """Tests for Context.on_event callback."""

    def test_context_accepts_on_event_callback(self):
        """Test that Context accepts on_event callback."""
        events = []
        ctx = Context(
            toolsets=[],
            model="test-model",
            on_event=lambda e: events.append(e),
        )
        assert ctx.on_event is not None

    def test_context_on_event_defaults_to_none(self):
        """Test that on_event defaults to None."""
        ctx = Context(toolsets=[], model="test-model")
        assert ctx.on_event is None

    def test_context_from_entry_accepts_on_event(self):
        """Test that Context.from_entry accepts on_event."""
        events = []
        worker = WorkerEntry(
            name="test",
            instructions="Test worker",
            model="test-model",
        )
        ctx = Context.from_entry(
            worker,
            on_event=lambda e: events.append(e),
        )
        assert ctx.on_event is not None

    def test_child_context_inherits_on_event(self):
        """Test that child contexts inherit on_event callback."""
        events = []
        callback = lambda e: events.append(e)
        ctx = Context(
            toolsets=[],
            model="test-model",
            on_event=callback,
        )
        child = ctx._child()
        assert child.on_event is callback

    def test_child_context_inherits_verbosity(self):
        """Test that child contexts inherit verbosity."""
        ctx = Context(
            toolsets=[],
            model="test-model",
            verbosity=2,
        )
        child = ctx._child()
        assert child.verbosity == 2


class TestWorkerEntryToolEvents:
    """Tests for ToolCallEvent/ToolResultEvent emission from WorkerEntry."""

    @pytest.mark.anyio
    async def test_worker_emits_tool_call_event(self):
        """Test that WorkerEntry emits ToolCallEvent when tools are called."""
        events: list[UIEvent] = []

        # Create a toolset with a simple tool
        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        # Create worker with the toolset
        worker = WorkerEntry(
            name="calculator",
            instructions="You are a calculator. Use add tool.",
            model=TestModel(call_tools=["add"]),
            toolsets=[toolset],
        )

        ctx = Context.from_entry(
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
        """Test that WorkerEntry emits events for multiple tool calls."""
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

        worker = WorkerEntry(
            name="calculator",
            instructions="You are a calculator.",
            model=TestModel(call_tools=["add", "multiply"]),
            toolsets=[toolset],
        )

        ctx = Context.from_entry(
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

        worker = WorkerEntry(
            name="greeter",
            instructions="Greet the user.",
            model=TestModel(call_tools=["greet"]),
            toolsets=[toolset],
        )

        ctx = Context.from_entry(
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

        worker = WorkerEntry(
            name="echo",
            instructions="Echo the input.",
            model=TestModel(call_tools=["echo"]),
            toolsets=[toolset],
        )

        # No on_event callback
        ctx = Context.from_entry(worker)
        assert ctx.on_event is None

        # Should not crash
        result = await ctx.run(worker, {"input": "Hello"})
        assert result is not None


class TestWorkerEntryStreamingEvents:
    """Tests for TextResponseEvent emission during streaming."""

    @pytest.mark.anyio
    async def test_streaming_emits_text_response_events(self):
        """Test that streaming mode emits TextResponseEvent deltas."""
        events: list[UIEvent] = []

        worker = WorkerEntry(
            name="assistant",
            instructions="Respond to the user.",
            model=TestModel(custom_output_text="Hello there!"),
            toolsets=[],
        )

        ctx = Context.from_entry(
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

    @pytest.mark.anyio
    async def test_no_streaming_without_verbosity(self):
        """Test that verbosity < 2 doesn't stream (still emits tool events)."""
        events: list[UIEvent] = []

        worker = WorkerEntry(
            name="assistant",
            instructions="Respond to the user.",
            model=TestModel(custom_output_text="Hello!"),
            toolsets=[],
        )

        ctx = Context.from_entry(
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
        from llm_do.ctx_runtime.cli import run
        from pathlib import Path

        events: list[UIEvent] = []

        # Use the greeter example
        examples_dir = Path(__file__).parent.parent.parent / "examples-new"
        worker_path = str(examples_dir / "greeter" / "main.worker")

        # Patch the model to use TestModel
        import llm_do.ctx_runtime.cli as cli_module
        original_build = cli_module.build_entry

        async def patched_build(*args, **kwargs):
            entry = await original_build(*args, **kwargs)
            entry.model = TestModel(custom_output_text="Hello!")
            return entry

        cli_module.build_entry = patched_build
        try:
            result, ctx = await run(
                files=[worker_path],
                prompt="Hi there",
                on_event=lambda e: events.append(e),
                verbosity=1,
            )
        finally:
            cli_module.build_entry = original_build

        assert result is not None
        # Events list may be empty for simple worker without tools
        # but on_event was accepted and wired up

    @pytest.mark.anyio
    async def test_run_with_tools_emits_events(self):
        """Test that run() with tools emits ToolCallEvent/ToolResultEvent."""
        from llm_do.ctx_runtime.cli import run
        from pathlib import Path

        events: list[UIEvent] = []

        # Use the calculator example
        examples_dir = Path(__file__).parent.parent.parent / "examples-new"
        worker_path = str(examples_dir / "calculator" / "main.worker")
        tools_path = str(examples_dir / "calculator" / "tools.py")

        # Patch to use TestModel that calls tools
        import llm_do.ctx_runtime.cli as cli_module
        original_build = cli_module.build_entry

        async def patched_build(*args, **kwargs):
            entry = await original_build(*args, **kwargs)
            entry.model = TestModel(
                call_tools=["add"],
                custom_output_text="The sum is 7.",
            )
            return entry

        cli_module.build_entry = patched_build
        try:
            result, ctx = await run(
                files=[worker_path, tools_path],
                prompt="Add 3 and 4",
                on_event=lambda e: events.append(e),
                verbosity=1,
                approve_all=True,  # Auto-approve tools for testing
            )
        finally:
            cli_module.build_entry = original_build

        # Should have tool events
        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        assert len(tool_calls) >= 1, f"Expected ToolCallEvent, got: {events}"
        assert len(tool_results) >= 1, f"Expected ToolResultEvent, got: {events}"
