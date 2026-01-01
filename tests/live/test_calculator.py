"""Live tests for the calculator example.

Tests custom tool integration with real LLM API calls.

Run:
    pytest tests/live/test_calculator.py -v
"""

import asyncio

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
