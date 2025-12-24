"""Tests for Context."""
import pytest
from pydantic_ai.toolsets import FunctionToolset

from llm_do.ctx_runtime import Context


class TestContext:
    """Tests for Context class."""

    def test_context_max_depth(self):
        """Test max_depth is set correctly."""
        ctx = Context(toolsets=[], model="test-model", max_depth=3)
        assert ctx.max_depth == 3
        assert ctx.depth == 0

    def test_context_child(self):
        """Test child context creation."""
        ctx = Context(toolsets=[], model="test-model", max_depth=5, depth=1)
        child = ctx._child()
        assert child.depth == 2
        assert child.max_depth == 5
        assert child.model == "test-model"

    @pytest.mark.anyio
    async def test_context_call_tool(self):
        """Test calling a tool through context."""
        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            return a * b

        ctx = Context(toolsets=[toolset], model="test-model")
        result = await ctx.call("multiply", {"a": 3, "b": 4})
        assert result == 12

    @pytest.mark.anyio
    async def test_context_tool_not_found(self):
        """Test that calling unknown tool raises KeyError."""
        ctx = Context(toolsets=[], model="test-model")
        with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
            await ctx.call("nonexistent", {"x": 1})

    @pytest.mark.anyio
    async def test_tools_proxy(self):
        """Test ToolsProxy attribute access."""
        toolset = FunctionToolset()

        @toolset.tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        ctx = Context(toolsets=[toolset], model="test-model")
        result = await ctx.tools.greet(name="World")
        assert result == "Hello, World!"
