"""Live tests for the calculator example.

Tests custom tool integration with real LLM API calls.

Includes regression test for verbosity=2 (streaming mode) with multi-turn
tool calls. See pydantic/pydantic-ai#2308 - run_stream() doesn't loop on
tool calls, so we must use run() with event_stream_handler instead.

Run:
    pytest tests/live/test_calculator.py -v
"""

import asyncio

import pytest
from pydantic_ai.messages import FunctionToolCallEvent, FunctionToolResultEvent

from .conftest import run_example, skip_no_llm


@skip_no_llm
def test_calculator_multiple_operations(calculator_example, default_model, approve_all_callback):
    """Test that calculator can handle multiple tool calls in one request.

    Uses large numbers that LLMs cannot know from training data,
    forcing actual tool usage.
    """
    result = asyncio.run(
        run_example(
            calculator_example,
            "Calculate the 50th Fibonacci number and 18 factorial",
            model=default_model,
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # 50th Fibonacci = 12586269025, 18! = 6402373705728000
    # These are large enough that LLMs cannot memorize them
    # Remove commas/spaces since LLMs often format large numbers for readability
    normalized = result.replace(",", "").replace(" ", "")
    assert "12586269025" in normalized
    assert "6402373705728000" in normalized


@skip_no_llm
@pytest.mark.anyio
async def test_calculator_verbosity_2(calculator_example, default_model):
    """Regression test: verbosity=2 must complete multi-turn tool calls.

    This failed before when verbosity>=2 used agent.run_stream() which
    doesn't loop on tool calls (pydantic/pydantic-ai#2308).
    """
    tool_calls = []
    tool_results = []

    def on_event(event):
        if isinstance(event.event, FunctionToolCallEvent):
            tool_calls.append(event.event.part.tool_name)
        elif isinstance(event.event, FunctionToolResultEvent):
            tool_results.append(event.event.result.tool_name)

    result = await run_example(
        calculator_example,
        "what is 15 * 7?",
        model=default_model,
        on_event=on_event,
        verbosity=2,  # This is the key - must work with streaming verbosity
    )

    # Must produce a result containing 105
    assert result is not None
    assert "105" in result

    # Must have made at least one tool call
    assert len(tool_calls) >= 1, f"Expected tool calls, got {tool_calls}"
    assert "multiply" in tool_calls

    # All tool calls must have corresponding results
    assert len(tool_results) == len(tool_calls)
