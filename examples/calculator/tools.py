"""Custom calculation tools for the calculator worker.

These tools are automatically registered by llm-do when the worker loads.
Each function becomes a tool that the LLM can call during execution.
"""


def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number.

    Args:
        n: The position in the Fibonacci sequence (must be >= 0)

    Returns:
        The Fibonacci number at position n

    Examples:
        calculate_fibonacci(0) -> 0
        calculate_fibonacci(1) -> 1
        calculate_fibonacci(10) -> 55
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n

    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def calculate_factorial(n: int) -> int:
    """Calculate the factorial of n (n!).

    Args:
        n: The number to calculate factorial for (must be >= 0)

    Returns:
        The factorial of n

    Examples:
        calculate_factorial(0) -> 1
        calculate_factorial(5) -> 120
        calculate_factorial(10) -> 3628800
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return 1

    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def calculate_prime_factors(n: int) -> list[int]:
    """Find all prime factors of a number.

    Args:
        n: The number to factorize (must be > 1)

    Returns:
        List of prime factors in ascending order

    Examples:
        calculate_prime_factors(12) -> [2, 2, 3]
        calculate_prime_factors(17) -> [17]
        calculate_prime_factors(100) -> [2, 2, 5, 5]
    """
    if n <= 1:
        raise ValueError("n must be greater than 1")

    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


# Private helper functions (starting with _) are not registered as tools
def _validate_input(n: int, min_value: int = 0) -> None:
    """Private helper function - not exposed as a tool."""
    if n < min_value:
        raise ValueError(f"Input must be >= {min_value}")
