"""Tests for call/runtime context behavior."""
import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import AgentSpec, EntrySpec, Runtime, ToolsetSpec, WorkerRuntime
from tests.runtime.helpers import build_call_scope


class TestContext:
    """Tests for call scope behavior."""

    @pytest.mark.anyio
    async def test_context_call_tool(self):
        """Test calling a tool through a call scope."""
        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            return a * b

        scope = build_call_scope(toolsets=[toolset], model="test")
        async with scope:
            result = await scope.call_tool("multiply", {"a": 3, "b": 4})
            assert result == 12

    @pytest.mark.anyio
    async def test_context_tool_not_found(self):
        """Test that calling unknown tool raises KeyError."""
        scope = build_call_scope(toolsets=[], model="test")
        async with scope:
            with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
                await scope.call_tool("nonexistent", {"x": 1})

    @pytest.mark.anyio
    async def test_call_with_kwargs(self):
        """Test calling a tool with keyword arguments."""
        toolset = FunctionToolset()

        @toolset.tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        scope = build_call_scope(toolsets=[toolset], model="test")
        async with scope:
            result = await scope.call_tool("greet", {"name": "World"})
            assert result == "Hello, World!"

    @pytest.mark.anyio
    async def test_context_call_tool_conflict_raises(self):
        """Test that duplicate tool names raise a conflict error."""
        toolset_a = FunctionToolset()
        toolset_b = FunctionToolset()

        @toolset_a.tool(name="clash")
        def clash_a() -> str:
            return "a"

        @toolset_b.tool(name="clash")
        def clash_b() -> str:
            return "b"

        scope = build_call_scope(toolsets=[toolset_a, toolset_b], model="test")
        async with scope:
            with pytest.raises(UserError, match="conflicts with existing tool"):
                await scope.call_tool("clash", {})

    @pytest.mark.anyio
    async def test_depth_counts_only_agents(self):
        """Test that depth increments only for call_agent invocations."""
        seen: dict[str, int] = {}

        def build_toolset(_ctx: object) -> FunctionToolset:
            toolset = FunctionToolset()

            @toolset.tool
            async def probe(ctx: RunContext[WorkerRuntime]) -> int:
                depth = ctx.deps.frame.config.depth
                seen["probe_depth"] = depth
                return depth

            return toolset

        toolset_spec = ToolsetSpec(factory=build_toolset)

        agent_spec = AgentSpec(
            name="depth-checker",
            instructions="Call probe.",
            model=TestModel(call_tools=["probe"], custom_output_text="done"),
            toolset_specs=[toolset_spec],
        )

        async def main(input_data, runtime: WorkerRuntime) -> str:
            seen["entry_depth"] = runtime.frame.config.depth
            return await runtime.call_agent(agent_spec, input_data)

        entry_spec = EntrySpec(name="entry", main=main)

        runtime = Runtime()
        await runtime.run_entry(entry_spec, {"input": "go"})

        assert seen["entry_depth"] == 0
        assert seen["probe_depth"] == 1
