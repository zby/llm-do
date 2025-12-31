"""Tests for Context."""
import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.ctx_runtime import Context, WorkerInvocable


class TestContext:
    """Tests for Context class."""

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

    @pytest.mark.anyio
    async def test_depth_counts_only_workers(self):
        """Test that depth increments only for worker calls."""
        toolset = FunctionToolset()
        seen: dict[str, dict[str, int] | int] = {}

        @toolset.tool
        async def probe(ctx: RunContext[Context]) -> int:
            depth = ctx.deps.depth
            seen["probe"] = depth
            return depth

        @toolset.tool
        async def call_probe(ctx: RunContext[Context]) -> dict[str, int]:
            before = ctx.deps.depth
            probe_depth = await ctx.deps.call("probe", {})
            after = ctx.deps.depth
            seen["call_probe"] = {"before": before, "probe": probe_depth, "after": after}
            return seen["call_probe"]

        worker = WorkerInvocable(
            name="depth-checker",
            instructions="Call call_probe.",
            model=TestModel(call_tools=["call_probe"], custom_output_text="done"),
            toolsets=[toolset],
        )
        ctx = Context.from_entry(worker)
        await ctx.run(worker, {"input": "go"})

        assert seen["call_probe"] == {"before": 1, "probe": 1, "after": 1}
        assert seen["probe"] == 1
