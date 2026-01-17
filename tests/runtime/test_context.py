"""Tests for WorkerRuntime."""
import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import ToolsetSpec, Worker, WorkerInput, WorkerRuntime
from tests.runtime.helpers import build_runtime_context, run_entry_test


class TestContext:
    """Tests for WorkerRuntime class."""

    @pytest.mark.anyio
    async def test_context_call_tool(self):
        """Test calling a tool through context."""
        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            return a * b

        ctx = build_runtime_context(toolsets=[toolset], model="test")
        result = await ctx.call("multiply", {"a": 3, "b": 4})
        assert result == 12

    @pytest.mark.anyio
    async def test_context_tool_not_found(self):
        """Test that calling unknown tool raises KeyError."""
        ctx = build_runtime_context(toolsets=[], model="test")
        with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
            await ctx.call("nonexistent", {"x": 1})

    @pytest.mark.anyio
    async def test_call_with_kwargs(self):
        """Test calling a tool with keyword arguments."""
        toolset = FunctionToolset()

        @toolset.tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        ctx = build_runtime_context(toolsets=[toolset], model="test")
        result = await ctx.call("greet", {"name": "World"})
        assert result == "Hello, World!"

    @pytest.mark.anyio
    async def test_depth_counts_only_workers(self):
        """Test that depth increments only for worker calls."""
        seen: dict[str, dict[str, int] | int] = {}

        def build_toolset(_ctx: object) -> FunctionToolset:
            toolset = FunctionToolset()

            @toolset.tool
            async def probe(run_ctx: RunContext[WorkerRuntime]) -> int:
                depth = run_ctx.deps.frame.depth
                seen["probe"] = depth
                return depth

            @toolset.tool
            async def call_probe(run_ctx: RunContext[WorkerRuntime]) -> dict[str, int]:
                before = run_ctx.deps.frame.depth
                probe_depth = await run_ctx.deps.call("probe", {})
                after = run_ctx.deps.frame.depth
                seen["call_probe"] = {
                    "before": before,
                    "probe": probe_depth,
                    "after": after,
                }
                return seen["call_probe"]

            return toolset

        toolset_spec = ToolsetSpec(factory=build_toolset)

        worker = Worker(
            name="depth-checker",
            instructions="Call call_probe.",
            model=TestModel(call_tools=["call_probe"], custom_output_text="done"),
            toolset_specs=[toolset_spec],
        )
        await run_entry_test(worker, WorkerInput(input="go"))

        assert seen["call_probe"] == {"before": 0, "probe": 0, "after": 0}
        assert seen["probe"] == 0
