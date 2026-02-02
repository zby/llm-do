"""Calculator tools using FunctionToolset."""
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import CallContext
from llm_do.toolsets.approval import set_toolset_approval_config


def build_calc_tools(_ctx: RunContext[CallContext]) -> FunctionToolset:
    calc_tools = FunctionToolset()

    @calc_tools.tool
    def factorial(n: int) -> int:
        """Calculate factorial of n.

        Args:
            n: Non-negative integer to calculate factorial of
        """
        if n < 0:
            raise ValueError("Factorial is not defined for negative numbers")
        if n <= 1:
            return 1
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

    @calc_tools.tool
    def fibonacci(n: int) -> int:
        """Calculate the nth Fibonacci number.

        Args:
            n: Position in Fibonacci sequence (0-indexed)
        """
        if n < 0:
            raise ValueError("Fibonacci is not defined for negative numbers")
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    @calc_tools.tool
    def add(a: float, b: float) -> float:
        """Add two numbers.

        Args:
            a: First number
            b: Second number
        """
        return a + b

    @calc_tools.tool
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers.

        Args:
            a: First number
            b: Second number
        """
        return a * b

    set_toolset_approval_config(
        calc_tools,
        {
            "factorial": {"pre_approved": True},
            "fibonacci": {"pre_approved": True},
            "add": {"pre_approved": True},
            "multiply": {"pre_approved": True},
        },
    )

    return calc_tools


TOOLSETS = {"calc_tools": build_calc_tools}
