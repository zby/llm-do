"""Tests for call/runtime context behavior."""
import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import AgentSpec, EntrySpec, Runtime, ToolsetSpec, WorkerRuntime


class TestContext:
    """Tests for call scope behavior."""

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
