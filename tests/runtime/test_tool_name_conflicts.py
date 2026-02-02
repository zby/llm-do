from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import AgentSpec, FunctionEntry, Runtime


def dupe() -> str:
    return "ok"


@pytest.mark.anyio
async def test_duplicate_tool_names_fail_fast() -> None:
    toolset = FunctionToolset()

    @toolset.tool
    def dupe() -> str:  # type: ignore[override]
        return "toolset"

    agent_spec = AgentSpec(
        name="conflict",
        instructions="Use tools.",
        model=TestModel(call_tools=["dupe"], custom_output_text="done"),
        tools=[dupe],
        toolsets=[toolset],
    )

    async def main(input_data, runtime):
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime()
    runtime.register_agents({agent_spec.name: agent_spec})

    with pytest.raises(ValueError, match="Duplicate tool names detected"):
        await runtime.run_entry(entry, {"input": "go"})
