"""Live tests for the calculator example.

Tests custom tool integration with real LLM API calls.

Run:
    pytest tests/live/test_calculator.py -v
"""

import asyncio

from llm_do import run_worker_async

from .conftest import skip_no_llm


@skip_no_llm
def test_calculator_multiple_operations(calculator_registry, default_model, approve_all_controller):
    """Test that calculator can handle multiple tool calls in one request."""
    result = asyncio.run(
        run_worker_async(
            registry=calculator_registry,
            worker="main",
            input_data="Calculate the 8th Fibonacci number and 5 factorial",
            cli_model=default_model,
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # 8th Fibonacci = 21, 5! = 120
    assert "21" in result.output
    assert "120" in result.output
