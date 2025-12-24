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
