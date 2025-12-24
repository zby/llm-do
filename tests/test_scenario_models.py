"""Tests for scenario-based test models."""
import pytest
from pydantic_ai import Agent
from pydantic_ai.toolsets import FunctionToolset

from tests.conftest_models import (
    Scenario,
    ToolCall,
    create_scenario_model,
    create_calculator_model,
    ConversationModel,
)


class TestScenarioModel:
    """Test the scenario-based model."""

    def test_matches_pattern_and_returns_text(self):
        model = create_scenario_model([
            Scenario(pattern=r"hello", response="Hi there!"),
            Scenario(pattern=r"goodbye", response="See you later!"),
        ])

        agent = Agent(model=model)

        result = agent.run_sync("hello world")
        assert "Hi there!" in result.output

        result = agent.run_sync("goodbye friend")
        assert "See you later!" in result.output

    def test_default_response_when_no_match(self):
        model = create_scenario_model(
            scenarios=[Scenario(pattern=r"specific", response="matched")],
            default_response="No match found",
        )

        agent = Agent(model=model)
        result = agent.run_sync("something else entirely")
        assert "No match found" in result.output

    def test_scenario_with_tool_call(self):
        model = create_scenario_model([
            Scenario(
                pattern=r"search for (\w+)",
                tool_calls=[ToolCall("search", {"query": "test"})],
                response="Found results!",
            ),
        ])

        toolset = FunctionToolset()

        @toolset.tool
        def search(query: str) -> str:
            """Search for something."""
            return f"Results for: {query}"

        agent = Agent(model=model, toolsets=[toolset])
        result = agent.run_sync("search for something")
        assert "Found results!" in result.output or "Results for" in result.output


class TestCalculatorModel:
    """Test the calculator-specific model."""

    @pytest.fixture
    def calculator_agent(self):
        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        @toolset.tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        @toolset.tool
        def factorial(n: int) -> int:
            """Calculate factorial."""
            if n <= 1:
                return 1
            result = 1
            for i in range(2, n + 1):
                result *= i
            return result

        return Agent(
            model=create_calculator_model(),
            toolsets=[toolset],
        )

    def test_multiply_extracts_numbers(self, calculator_agent):
        result = calculator_agent.run_sync("multiply 7 by 8")
        # The model should call multiply(7, 8) and get 56
        assert "56" in str(result.output) or result.output == 56

    def test_add_extracts_numbers(self, calculator_agent):
        result = calculator_agent.run_sync("add 100 and 50")
        assert "150" in str(result.output) or result.output == 150

    def test_factorial_extracts_number(self, calculator_agent):
        result = calculator_agent.run_sync("factorial of 5")
        assert "120" in str(result.output) or result.output == 120

    def test_unknown_operation_returns_help(self, calculator_agent):
        result = calculator_agent.run_sync("what is the meaning of life")
        assert "multiply" in result.output.lower() or "add" in result.output.lower()


class TestWorkerEntryWithScenarioModel:
    """Test using scenario models with WorkerEntry for integration testing."""

    @pytest.mark.anyio
    async def test_worker_with_calculator_model(self):
        """Test WorkerEntry uses scenario model to call tools correctly."""
        from llm_do.ctx_runtime import Context, WorkerEntry

        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        worker = WorkerEntry(
            name="calc",
            instructions="You are a calculator.",
            model=create_calculator_model(),
            toolsets=[toolset],
        )

        ctx = Context.from_entry(worker)
        result = await ctx.run(worker, {"input": "multiply 6 by 7"})
        assert "42" in str(result)

    @pytest.mark.anyio
    async def test_worker_emits_events_with_scenario_model(self):
        """Test that events are emitted even with scenario models."""
        from llm_do.ctx_runtime import Context, WorkerEntry
        from llm_do.ui.events import ToolCallEvent, ToolResultEvent

        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        events = []

        worker = WorkerEntry(
            name="calc",
            instructions="You are a calculator.",
            model=create_calculator_model(),
            toolsets=[toolset],
        )

        ctx = Context.from_entry(worker, on_event=events.append, verbosity=1)
        result = await ctx.run(worker, {"input": "add 10 and 20"})
        assert "30" in str(result)

        # Verify events were emitted
        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        assert len(tool_calls) >= 1
        assert len(tool_results) >= 1
        assert tool_calls[0].tool_name == "add"
        assert tool_calls[0].args == {"a": 10, "b": 20}


class TestStreamingModels:
    """Test streaming support in scenario models."""

    @pytest.mark.anyio
    async def test_streaming_text_response(self):
        """Test that streaming model yields text chunks."""
        model = create_scenario_model(
            scenarios=[Scenario(pattern=r"hello", response="Hello there, friend!")],
            streaming=True,
        )

        agent = Agent(model=model)

        chunks = []
        async with agent.run_stream("hello world") as stream:
            async for chunk in stream.stream_text(delta=True):
                chunks.append(chunk)

        # Should have received multiple chunks
        assert len(chunks) >= 1
        # Combined should be the full response
        assert "Hello there" in "".join(chunks)

    @pytest.mark.anyio
    async def test_streaming_events_no_complete_event(self):
        """Test that streaming deltas don't also emit a complete event.

        When streaming with verbosity=2, we should see streaming deltas
        but NOT a final "complete" TextResponseEvent (which would duplicate output).
        """
        from llm_do.ctx_runtime import Context, WorkerEntry
        from llm_do.ui.events import TextResponseEvent

        events = []

        worker = WorkerEntry(
            name="helper",
            instructions="You are a helper.",
            model=create_scenario_model(
                scenarios=[Scenario(pattern=r".*", response="Hello world!")],
                streaming=True,
            ),
            toolsets=[],
        )

        # verbosity=2 enables streaming
        ctx = Context.from_entry(worker, on_event=events.append, verbosity=2)
        result = await ctx.run(worker, {"input": "say hello"})

        # The result should be "Hello world!"
        assert "Hello" in result

        # Analyze events
        delta_events = [e for e in events
                       if isinstance(e, TextResponseEvent) and e.is_delta]
        complete_events = [e for e in events
                          if isinstance(e, TextResponseEvent) and e.is_complete]

        # We should have delta events (streaming chunks)
        assert len(delta_events) >= 1, "Should have streaming delta events"

        # KEY ASSERTION: When streaming, we should NOT also emit a "complete" event
        # because that would cause duplicate display (streaming chunks + full response)
        assert len(complete_events) == 0, (
            f"Should not have complete TextResponseEvent when streaming, "
            f"but got {len(complete_events)}: {[e.content for e in complete_events]}"
        )

    def test_cli_no_duplicate_output_when_streaming(self):
        """Test that CLI doesn't print result twice when streaming.

        When using -vv (streaming), the streamed text appears via events,
        and print(result) should be suppressed to avoid duplication.
        """
        import io
        import sys
        from unittest.mock import patch

        # Create a simple worker file
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            worker_path = os.path.join(tmpdir, "test.worker")
            with open(worker_path, "w") as f:
                f.write("""---
name: main
---
You are a helper.
""")

            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            # Mock sys.argv to simulate CLI invocation
            test_args = [
                "llm-run",
                worker_path,
                "-vv",
                "say hello",
            ]

            # We need to patch the model to use our test model
            # and capture the output
            from llm_do.ctx_runtime import cli

            # Patch build_entry to return a worker with our test model
            original_build_entry = cli.build_entry

            async def patched_build_entry(*args, **kwargs):
                from llm_do.ctx_runtime import WorkerEntry
                return WorkerEntry(
                    name="main",
                    instructions="You are a helper.",
                    model=create_scenario_model(
                        scenarios=[Scenario(pattern=r".*", response="Hello world!")],
                        streaming=True,
                    ),
                    toolsets=[],
                )

            with patch.object(cli, 'build_entry', patched_build_entry):
                with patch.object(sys, 'argv', test_args):
                    with patch.object(sys, 'stdout', stdout_capture):
                        with patch.object(sys, 'stderr', stderr_capture):
                            cli.main()

            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            # The streaming output goes to stderr (via HeadlessDisplayBackend)
            # The final print(result) goes to stdout

            # When streaming is active, stdout should be empty
            # (no duplicate print of the result)
            assert stdout_output.strip() == "", (
                f"Expected no stdout when streaming, but got: {repr(stdout_output)}"
            )

            # stderr should have the streamed content
            assert "Hello" in stderr_output, (
                f"Expected streaming output in stderr, but got: {repr(stderr_output)}"
            )

    @pytest.mark.anyio
    async def test_streaming_calculator_with_tool(self):
        """Test streaming calculator calls tools and streams result."""
        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        model = create_calculator_model(streaming=True)
        agent = Agent(model=model, toolsets=[toolset])

        chunks = []
        async with agent.run_stream("multiply 5 by 5") as stream:
            async for chunk in stream.stream_text(delta=True):
                chunks.append(chunk)
            output = await stream.get_output()

        # Should get the result
        assert "25" in str(output) or "25" in "".join(chunks)

    @pytest.mark.anyio
    async def test_streaming_worker_entry(self):
        """Test WorkerEntry streaming with scenario model."""
        from llm_do.ctx_runtime import Context, WorkerEntry
        from llm_do.ui.events import TextResponseEvent

        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        events = []

        worker = WorkerEntry(
            name="calc",
            instructions="You are a calculator.",
            model=create_calculator_model(streaming=True),
            toolsets=[toolset],
        )

        # verbosity=2 enables streaming
        ctx = Context.from_entry(worker, on_event=events.append, verbosity=2)
        result = await ctx.run(worker, {"input": "add 7 and 8"})

        # Should have text response events from streaming
        text_events = [e for e in events if isinstance(e, TextResponseEvent)]
        assert len(text_events) >= 1

        # Result should contain 15
        assert "15" in str(result)


class TestConversationModel:
    """Test multi-turn conversation model."""

    def test_multi_turn_responses(self):
        from pydantic_ai.messages import ModelResponse, TextPart

        conv = ConversationModel(turns=[
            lambda p, m, i: ModelResponse(parts=[TextPart(content="First response")]),
            lambda p, m, i: ModelResponse(parts=[TextPart(content="Second response")]),
            lambda p, m, i: ModelResponse(parts=[TextPart(content="Third response")]),
        ])

        agent = Agent(model=conv.to_model())

        r1 = agent.run_sync("turn 1")
        assert "First" in r1.output

        r2 = agent.run_sync("turn 2")
        assert "Second" in r2.output

        r3 = agent.run_sync("turn 3")
        assert "Third" in r3.output

    def test_reset_restarts_conversation(self):
        from pydantic_ai.messages import ModelResponse, TextPart

        conv = ConversationModel(turns=[
            lambda p, m, i: ModelResponse(parts=[TextPart(content="First")]),
            lambda p, m, i: ModelResponse(parts=[TextPart(content="Second")]),
        ])

        agent = Agent(model=conv.to_model())

        r1 = agent.run_sync("turn 1")
        assert "First" in r1.output

        conv.reset()

        r2 = agent.run_sync("turn 1 again")
        assert "First" in r2.output  # Should be "First" again after reset
