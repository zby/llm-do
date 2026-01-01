"""Live tests for the calculator example.

Tests custom tool integration with real LLM API calls.

Run:
    pytest tests/live/test_calculator.py -v
"""

import asyncio

from .conftest import run_example, skip_no_llm


@skip_no_llm
def test_calculator_multiple_operations(calculator_example, default_model, approve_all_callback):
    """Test that calculator can handle multiple tool calls in one request."""
    result = asyncio.run(
        run_example(
            calculator_example,
            "Calculate the 8th Fibonacci number and 5 factorial",
            model=default_model,
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # 8th Fibonacci = 21, 5! = 120
    assert "21" in result
    assert "120" in result
