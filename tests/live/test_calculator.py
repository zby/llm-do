"""Live tests for the calculator example.

Tests custom tool integration with real LLM API calls.

Run:
    pytest tests/live/test_calculator.py -v
"""

import asyncio

from llm_do import run_worker_async

from .conftest import skip_no_llm


@skip_no_llm
def test_calculator_fibonacci(calculator_registry, default_model, approve_all_controller):
    """Test that calculator can compute Fibonacci numbers using custom tool."""
    result = asyncio.run(
        run_worker_async(
            registry=calculator_registry,
            worker="main",
            input_data="What is the 10th Fibonacci number?",
            cli_model=default_model,
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # The 10th Fibonacci number is 55
    assert "55" in result.output


@skip_no_llm
def test_calculator_factorial(calculator_registry, default_model, approve_all_controller):
    """Test that calculator can compute factorials using custom tool."""
    result = asyncio.run(
        run_worker_async(
            registry=calculator_registry,
            worker="main",
            input_data="What is 7 factorial?",
            cli_model=default_model,
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # 7! = 5040 (may be formatted as "5,040" or "5040")
    assert "5040" in result.output or "5,040" in result.output


@skip_no_llm
def test_calculator_prime_factors(calculator_registry, default_model, approve_all_controller):
    """Test that calculator can find prime factors using custom tool."""
    result = asyncio.run(
        run_worker_async(
            registry=calculator_registry,
            worker="main",
            input_data="What are the prime factors of 84?",
            cli_model=default_model,
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # 84 = 2 * 2 * 3 * 7
    # The result should mention these factors
    assert "2" in result.output
    assert "3" in result.output
    assert "7" in result.output


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
