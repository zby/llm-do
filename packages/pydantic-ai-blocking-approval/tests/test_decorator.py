"""Tests for @requires_approval decorator."""
import pytest

from pydantic_ai_blocking_approval import requires_approval


class TestRequiresApprovalDecorator:
    """Tests for the @requires_approval decorator (marker-only)."""

    def test_decorator_marks_function(self):
        """Decorator marks function with _requires_approval attribute."""

        @requires_approval
        def my_tool(arg: str) -> str:
            return f"done: {arg}"

        # Function should have _requires_approval attribute
        assert hasattr(my_tool, "_requires_approval")
        assert my_tool._requires_approval is True

    def test_decorated_function_still_works(self):
        """Decorated function can still be called normally."""

        @requires_approval
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_decorator_preserves_function_name(self):
        """Decorator preserves the function's name."""

        @requires_approval
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_unmarked_function_has_no_attribute(self):
        """Unmarked functions don't have the approval attribute."""

        def regular_function():
            pass

        assert not hasattr(regular_function, "_requires_approval")

    def test_decorator_works_with_async_functions(self):
        """Decorator works with async functions."""

        @requires_approval
        async def async_tool(path: str) -> str:
            return f"processed {path}"

        assert hasattr(async_tool, "_requires_approval")
        assert async_tool._requires_approval is True
