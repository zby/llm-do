"""Tests for scenario-based test models."""
import pytest
from pydantic_ai import Agent
from pydantic_ai.toolsets import FunctionToolset

from tests.conftest_models import (
    ConversationModel,
    Scenario,
    ToolCall,
    create_calculator_model,
    create_scenario_model,
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

        return Agent(
            model=create_calculator_model(),
            toolsets=[toolset],
        )

    def test_multiply_extracts_numbers(self, calculator_agent):
        result = calculator_agent.run_sync("multiply 7 by 8")
        # The model should call multiply(7, 8) and get 56
        assert "56" in str(result.output) or result.output == 56

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
    async def test_streaming_events_include_complete_event(self):
        """Test that streaming deltas also emit a final complete event.

        When streaming with verbosity=2, we should see streaming deltas
        and a final "complete" TextResponseEvent to mark completion.
        """
        from llm_do.runtime import Worker, WorkerRuntime
        from llm_do.ui.events import TextResponseEvent

        events = []

        worker = Worker(
            name="helper",
            instructions="You are a helper.",
            model=create_scenario_model(
                scenarios=[Scenario(pattern=r".*", response="Hello world!")],
                streaming=True,
            ),
            toolsets=[],
        )

        # verbosity=2 enables streaming
        ctx = WorkerRuntime.from_entry(worker, on_event=events.append, verbosity=2)
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

        # KEY ASSERTION: When streaming, we should also emit a "complete" event
        # to provide a final response for logs and non-TUI displays.
        assert len(complete_events) >= 1, (
            "Expected complete TextResponseEvent when streaming, "
            "but none were emitted."
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
