"""Tests for CallRuntime and CallScope tool invocation."""
import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import CallRuntime, ToolsetSpec, entry
from tests.runtime.helpers import build_call_scope, run_entry_test


class TestContext:
    """Tests for CallScope tool invocation."""

    @pytest.mark.anyio
    async def test_context_call_tool(self):
        """Test calling a tool through CallScope."""
        toolset = FunctionToolset()

        @toolset.tool
        def multiply(a: int, b: int) -> int:
            return a * b

        scope = build_call_scope(toolsets=[toolset], model="test")
        result = await scope.call_tool("multiply", {"a": 3, "b": 4})
        assert result == 12

    @pytest.mark.anyio
    async def test_context_tool_not_found(self):
        """Test that calling unknown tool raises KeyError."""
        scope = build_call_scope(toolsets=[], model="test")
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
        with pytest.raises(UserError, match="conflicts with existing tool"):
            await scope.call_tool("clash", {})

    @pytest.mark.anyio
    async def test_depth_counts_only_agents(self):
        """Test that depth increments only for agent calls."""
        seen: dict[str, dict[str, int] | int] = {}

        def build_toolset(_ctx: object) -> FunctionToolset:
            toolset = FunctionToolset()

            @toolset.tool
            async def probe(run_ctx: RunContext[CallRuntime]) -> int:
                depth = run_ctx.deps.frame.config.depth
                seen["probe"] = depth
                return depth

            return toolset

        toolset_spec = ToolsetSpec(factory=build_toolset)

        @entry(toolsets=[toolset_spec])
        async def main(_args, scope) -> dict[str, int]:
            before = scope.runtime.frame.config.depth
            probe_depth = await scope.call_tool("probe", {})
            after = scope.runtime.frame.config.depth
            result: dict[str, int] = {
                "before": before,
                "probe": probe_depth,
                "after": after,
            }
            seen["call_probe"] = result
            return result

        await run_entry_test(main, {"input": "go"})

        assert seen["call_probe"] == {"before": 0, "probe": 0, "after": 0}
        assert seen["probe"] == 0
