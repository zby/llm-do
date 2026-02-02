"""Tests for the dynamic_agents toolset."""
from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from llm_do.runtime import RunApprovalPolicy, Runtime
from llm_do.toolsets.builtins import build_builtin_toolsets
from llm_do.toolsets.dynamic_agents import (
    AgentCallArgs,
    AgentCreateArgs,
    DynamicAgentsToolset,
)


@pytest.mark.anyio
async def test_dynamic_agent_create_and_call(tmp_path):
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        project_root=tmp_path,
        generated_agents_dir=tmp_path,
    )
    ctx = runtime.spawn_call_runtime(
        active_toolsets=[],
        model=TestModel(),
        invocation_name="test",
        depth=0,
    )

    toolset = DynamicAgentsToolset()
    name = toolset._agent_create(
        ctx,
        AgentCreateArgs(
            name="sample_agent",
            instructions="Return OK.",
            description="test agent",
            model="test",
        ),
    )

    assert (tmp_path / "sample_agent.agent").exists()
    assert name in ctx.dynamic_agents

    ctx.dynamic_agents[name].model = TestModel(custom_output_text="ok")
    result = await toolset._agent_call(
        ctx,
        AgentCallArgs(agent=name, input="hi"),
    )
    assert result == "ok"


@pytest.mark.anyio
async def test_dynamic_agent_create_validates_toolsets(tmp_path):
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        project_root=tmp_path,
        generated_agents_dir=tmp_path,
    )
    runtime.register_toolsets(build_builtin_toolsets(tmp_path, tmp_path))
    ctx = runtime.spawn_call_runtime(
        active_toolsets=[],
        model=TestModel(),
        invocation_name="test",
        depth=0,
    )

    toolset = DynamicAgentsToolset()
    name = toolset._agent_create(
        ctx,
        AgentCreateArgs(
            name="with_tools",
            instructions="Return OK.",
            description="toolset agent",
            model="test",
            toolsets=["filesystem_project"],
        ),
    )
    assert ctx.dynamic_agents[name].toolsets

    with pytest.raises(ValueError, match="Unknown toolset"):
        toolset._agent_create(
            ctx,
            AgentCreateArgs(
                name="bad_tools",
                instructions="Return OK.",
                description="bad tools",
                model="test",
                toolsets=["nope_toolset"],
            ),
        )


@pytest.mark.anyio
async def test_dynamic_agent_create_validates_tools(tmp_path):
    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        project_root=tmp_path,
        generated_agents_dir=tmp_path,
    )
    def ping():
        return "pong"

    runtime.register_tools({"ping": ping})
    ctx = runtime.spawn_call_runtime(
        active_toolsets=[],
        model=TestModel(),
        invocation_name="test",
        depth=0,
    )

    toolset = DynamicAgentsToolset()
    name = toolset._agent_create(
        ctx,
        AgentCreateArgs(
            name="with_tools",
            instructions="Return OK.",
            description="tool agent",
            model="test",
            tools=["ping"],
        ),
    )
    assert ctx.dynamic_agents[name].tools

    with pytest.raises(ValueError, match="Unknown tool"):
        toolset._agent_create(
            ctx,
            AgentCreateArgs(
                name="bad_tools",
                instructions="Return OK.",
                description="bad tools",
                model="test",
                tools=["nope_tool"],
            ),
        )
