"""Tests for Context and CallTrace."""
import pytest
from pydantic_ai.toolsets import FunctionToolset

from llm_do.ctx_runtime import Context, CallTrace


class TestCallTrace:
    """Tests for CallTrace dataclass."""

    def test_call_trace_creation(self):
        """Test creating a CallTrace."""
        trace = CallTrace(
            name="test_tool",
            kind="tool",
            depth=0,
            input_data={"x": 42},
        )
        assert trace.name == "test_tool"
        assert trace.kind == "tool"
        assert trace.depth == 0
        assert trace.input_data == {"x": 42}
        assert trace.output_data is None
        assert trace.error is None

    def test_call_trace_with_output(self):
        """Test CallTrace with output data."""
        trace = CallTrace(
            name="test_tool",
            kind="tool",
            depth=1,
            input_data={"x": 42},
            output_data=84,
        )
        assert trace.output_data == 84

    def test_call_trace_with_error(self):
        """Test CallTrace with error."""
        trace = CallTrace(
            name="test_tool",
            kind="tool",
            depth=0,
            input_data={"x": 42},
            error="Something went wrong",
        )
        assert trace.error == "Something went wrong"


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
        # Trace should be shared
        assert child.trace is ctx.trace

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
    async def test_context_trace(self):
        """Test that calls are traced."""
        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            return a + b

        ctx = Context(toolsets=[toolset], model="test-model")
        await ctx.call("add", {"a": 1, "b": 2})

        assert len(ctx.trace) == 1
        trace = ctx.trace[0]
        assert trace.name == "add"
        assert trace.kind == "tool"
        assert trace.input_data == {"a": 1, "b": 2}
        assert trace.output_data == 3

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
