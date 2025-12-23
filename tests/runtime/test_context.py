"""Tests for Context, Registry, and CallTrace."""
import pytest

from llm_do.ctx_runtime import Context, Registry, CallTrace, ToolEntry, tool_entry


class TestRegistry:
    """Tests for the Registry class."""

    def test_register_and_get(self):
        """Test basic registration and retrieval."""
        registry = Registry()

        @tool_entry()
        def my_tool(x: int) -> int:
            return x * 2

        registry.register(my_tool)
        assert registry.get("my_tool") is my_tool

    def test_duplicate_name_raises(self):
        """Test that duplicate names raise ValueError."""
        registry = Registry()

        @tool_entry()
        def my_tool(x: int) -> int:
            return x * 2

        @tool_entry(name="my_tool")
        def another_tool(x: int) -> int:
            return x * 3

        registry.register(my_tool)
        with pytest.raises(ValueError, match="Duplicate entry name"):
            registry.register(another_tool)

    def test_unknown_name_raises(self):
        """Test that unknown names raise KeyError."""
        registry = Registry()
        with pytest.raises(KeyError, match="Unknown entry"):
            registry.get("nonexistent")

    def test_contains(self):
        """Test __contains__ method."""
        registry = Registry()

        @tool_entry()
        def my_tool(x: int) -> int:
            return x * 2

        registry.register(my_tool)
        assert "my_tool" in registry
        assert "other" not in registry

    def test_list_names(self):
        """Test list_names method."""
        registry = Registry()

        @tool_entry()
        def tool_a(x: int) -> int:
            return x

        @tool_entry()
        def tool_b(x: int) -> int:
            return x

        registry.register(tool_a)
        registry.register(tool_b)
        names = registry.list_names()
        assert set(names) == {"tool_a", "tool_b"}


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


class TestToolEntry:
    """Tests for ToolEntry and tool_entry decorator."""

    def test_tool_entry_decorator(self):
        """Test basic tool_entry decorator."""
        @tool_entry()
        def double(x: int) -> int:
            """Double a number."""
            return x * 2

        assert double.name == "double"
        assert double.kind == "tool"
        assert double.requires_approval is False

    def test_tool_entry_with_name(self):
        """Test tool_entry with custom name."""
        @tool_entry(name="custom_name")
        def my_func(x: int) -> int:
            return x

        assert my_func.name == "custom_name"

    def test_tool_entry_with_approval(self):
        """Test tool_entry with requires_approval."""
        @tool_entry(requires_approval=True)
        def sensitive_tool(x: int) -> int:
            return x

        assert sensitive_tool.requires_approval is True


class TestContext:
    """Tests for Context class."""

    @pytest.mark.anyio
    async def test_context_from_tool_entries(self):
        """Test creating Context from tool entries."""
        @tool_entry()
        def add(a: int, b: int) -> int:
            return a + b

        ctx = Context.from_tool_entries([add], model="test-model")
        assert "add" in ctx.registry
        assert ctx.model == "test-model"

    def test_context_max_depth(self):
        """Test max_depth is set correctly."""
        ctx = Context(Registry(), model="test-model", max_depth=3)
        assert ctx.max_depth == 3
        assert ctx.depth == 0

    def test_context_child(self):
        """Test child context creation."""
        ctx = Context(Registry(), model="test-model", max_depth=5, depth=1)
        child = ctx._child()
        assert child.depth == 2
        assert child.max_depth == 5
        assert child.model == "test-model"
        # Trace should be shared
        assert child.trace is ctx.trace

    @pytest.mark.anyio
    async def test_context_call_tool(self):
        """Test calling a tool through context."""
        @tool_entry()
        def multiply(a: int, b: int) -> int:
            return a * b

        ctx = Context.from_tool_entries([multiply], model="test-model")
        result = await ctx.call("multiply", {"a": 3, "b": 4})
        assert result == 12

    @pytest.mark.anyio
    async def test_context_trace(self):
        """Test that calls are traced."""
        @tool_entry()
        def add(a: int, b: int) -> int:
            return a + b

        ctx = Context.from_tool_entries([add], model="test-model")
        await ctx.call("add", {"a": 1, "b": 2})

        assert len(ctx.trace) == 1
        trace = ctx.trace[0]
        assert trace.name == "add"
        assert trace.kind == "tool"
        assert trace.input_data == {"a": 1, "b": 2}
        assert trace.output_data == 3

    @pytest.mark.anyio
    async def test_context_approval_denied(self):
        """Test that approval denial raises PermissionError."""
        @tool_entry(requires_approval=True)
        def dangerous(x: int) -> int:
            return x

        # Create context that denies all approvals
        ctx = Context.from_tool_entries(
            [dangerous],
            model="test-model",
            approval=lambda entry, data: False,
        )

        with pytest.raises(PermissionError, match="Approval denied"):
            await ctx.call("dangerous", {"x": 42})

    @pytest.mark.anyio
    async def test_context_max_depth_exceeded(self):
        """Test that exceeding max depth raises RuntimeError."""
        ctx = Context(Registry(), model="test-model", max_depth=2, depth=2)

        @tool_entry()
        def simple(x: int) -> int:
            return x

        ctx.registry.register(simple)

        with pytest.raises(RuntimeError, match="Max depth exceeded"):
            await ctx.call("simple", {"x": 1})

    @pytest.mark.anyio
    async def test_tools_proxy(self):
        """Test ToolsProxy attribute access."""
        @tool_entry()
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        ctx = Context.from_tool_entries([greet], model="test-model")
        result = await ctx.tools.greet(name="World")
        assert result == "Hello, World!"
