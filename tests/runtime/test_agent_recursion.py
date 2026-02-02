import pytest
from pydantic_ai.models.test import TestModel

from llm_do.runtime import (
    AgentSpec,
    EntryConfig,
    FunctionEntry,
    Runtime,
    build_registry,
    resolve_entry,
)
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.toolsets.agent import AgentToolset, agent_as_toolset


@pytest.mark.anyio
async def test_registry_allows_self_toolset_reference(tmp_path) -> None:
    agent_path = tmp_path / "recursive.agent"
    agent_path.write_text(
        """---
name: recursive
model: test
toolsets:
  - recursive
---
Call yourself.
"""
    )

    registry = build_registry(
        [str(agent_path)],
        [],
        project_root=tmp_path,
    )
    entry = resolve_entry(
        EntryConfig(agent="recursive"),
        registry,
        python_files=[],
        base_path=tmp_path,
    )

    agent = registry.agents[entry.name]
    assert agent.toolsets
    toolset = agent.toolsets[0]
    from pydantic_ai.toolsets._dynamic import DynamicToolset
    if isinstance(toolset, DynamicToolset):
        from pydantic_ai._run_context import RunContext
        from pydantic_ai.usage import RunUsage
        toolset = toolset.toolset_func(
            RunContext(deps=None, model=TestModel(), usage=RunUsage())
        )
    assert isinstance(toolset, AgentToolset)
    assert toolset.spec is agent


@pytest.mark.anyio
async def test_max_depth_blocks_self_recursion() -> None:
    agent_spec = AgentSpec(
        name="loop",
        instructions="Loop until depth is exceeded.",
        model=TestModel(call_tools=["loop"], custom_output_text="done"),
        toolsets=[],
    )
    agent_spec.toolsets = [agent_as_toolset(agent_spec)]

    async def main(input_data, runtime):
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        max_depth=2,
    )
    runtime.register_agents({agent_spec.name: agent_spec})

    with pytest.raises(RuntimeError, match="max_depth exceeded"):
        await runtime.run_entry(entry, {"input": "go"})
