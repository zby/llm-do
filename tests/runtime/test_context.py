"""Tests for Context, Registry, and CallTrace."""
import pytest
from pydantic_ai.toolsets import FunctionToolset

from llm_do.ctx_runtime import Context, Registry, CallTrace, ToolsetToolEntry, expand_toolset_to_entries


class TestRegistry:
    """Tests for the Registry class."""

    @pytest.mark.anyio
    async def test_register_and_get(self):
        """Test basic registration and retrieval."""
        registry = Registry()

        toolset = FunctionToolset()

        @toolset.tool
        def my_tool(x: int) -> int:
            return x * 2

        entries = await expand_toolset_to_entries(toolset)
        entry = entries[0]
        registry.register(entry)
        assert registry.get("my_tool") is entry

    @pytest.mark.anyio
    async def test_duplicate_name_raises(self):
        """Test that duplicate names raise ValueError."""
        registry = Registry()

        toolset = FunctionToolset()

        @toolset.tool
        def my_tool(x: int) -> int:
            return x * 2

        entries = await expand_toolset_to_entries(toolset)
        entry = entries[0]

        registry.register(entry)
        with pytest.raises(ValueError, match="Duplicate entry name"):
            registry.register(entry)

    def test_unknown_name_raises(self):
        """Test that unknown names raise KeyError."""
        registry = Registry()
        with pytest.raises(KeyError, match="Unknown entry"):
            registry.get("nonexistent")

    @pytest.mark.anyio
    async def test_contains(self):
        """Test __contains__ method."""
        registry = Registry()

        toolset = FunctionToolset()

        @toolset.tool
        def my_tool(x: int) -> int:
            return x * 2

        entries = await expand_toolset_to_entries(toolset)
        registry.register(entries[0])
        assert "my_tool" in registry
        assert "other" not in registry

    @pytest.mark.anyio
    async def test_list_names(self):
        """Test list_names method."""
        registry = Registry()

        toolset = FunctionToolset()

        @toolset.tool
        def tool_a(x: int) -> int:
            return x

        @toolset.tool
        def tool_b(x: int) -> int:
            return x

        entries = await expand_toolset_to_entries(toolset)
        for entry in entries:
            registry.register(entry)
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


class TestToolsetToolEntry:
    """Tests for ToolsetToolEntry created from FunctionToolset."""

    @pytest.mark.anyio
    async def test_toolset_tool_entry_from_function_toolset(self):
        """Test creating ToolsetToolEntry from FunctionToolset."""
        toolset = FunctionToolset()

        @toolset.tool
        def double(x: int) -> int:
            """Double a number."""
            return x * 2

        entries = await expand_toolset_to_entries(toolset)
        entry = entries[0]

        assert entry.name == "double"
        assert entry.kind == "tool"
        assert entry.requires_approval is False

    @pytest.mark.anyio
    async def test_toolset_tool_entry_with_approval(self):
        """Test ToolsetToolEntry with requires_approval."""
        toolset = FunctionToolset()

        @toolset.tool(requires_approval=True)
        def sensitive_tool(x: int) -> int:
            return x

        entries = await expand_toolset_to_entries(toolset)
        entry = entries[0]

        assert entry.requires_approval is True


class TestContext:
    """Tests for Context class."""

    @pytest.mark.anyio
    async def test_context_from_entry(self):
        """Test creating Context from entry with available tools."""
        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            return a + b

        entries = await expand_toolset_to_entries(toolset)
        add_entry = entries[0]

        # Create context with available tools
        ctx = Context.from_entry(add_entry, model="test-model", available=[add_entry])
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
        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            return a * b

        entries = await expand_toolset_to_entries(toolset)
        registry = Registry()
        for entry in entries:
            registry.register(entry)
        ctx = Context(registry, model="test-model")
        result = await ctx.call("multiply", {"a": 3, "b": 4})
        assert result == 12

    @pytest.mark.anyio
    async def test_context_trace(self):
        """Test that calls are traced."""
        toolset = FunctionToolset()

        @toolset.tool
        def add(a: int, b: int) -> int:
            return a + b

        entries = await expand_toolset_to_entries(toolset)
        registry = Registry()
        for entry in entries:
            registry.register(entry)
        ctx = Context(registry, model="test-model")
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
        toolset = FunctionToolset()

        @toolset.tool(requires_approval=True)
        def dangerous(x: int) -> int:
            return x

        entries = await expand_toolset_to_entries(toolset)
        # Create context that denies all approvals
        registry = Registry()
        for entry in entries:
            registry.register(entry)
        ctx = Context(
            registry,
            model="test-model",
            approval=lambda entry, data: False,
        )

        with pytest.raises(PermissionError, match="Approval denied"):
            await ctx.call("dangerous", {"x": 42})

    @pytest.mark.anyio
    async def test_context_max_depth_exceeded(self):
        """Test that exceeding max depth raises RuntimeError."""
        toolset = FunctionToolset()

        @toolset.tool
        def simple(x: int) -> int:
            return x

        entries = await expand_toolset_to_entries(toolset)
        registry = Registry()
        for entry in entries:
            registry.register(entry)
        ctx = Context(registry, model="test-model", max_depth=2, depth=2)

        with pytest.raises(RuntimeError, match="Max depth exceeded"):
            await ctx.call("simple", {"x": 1})

    @pytest.mark.anyio
    async def test_tools_proxy(self):
        """Test ToolsProxy attribute access."""
        toolset = FunctionToolset()

        @toolset.tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        entries = await expand_toolset_to_entries(toolset)
        registry = Registry()
        for entry in entries:
            registry.register(entry)
        ctx = Context(registry, model="test-model")
        result = await ctx.tools.greet(name="World")
        assert result == "Hello, World!"
