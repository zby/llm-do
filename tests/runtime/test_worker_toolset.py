"""Tests for AgentToolset adapter."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext

from llm_do.runtime import AgentSpec, ToolsetBuildContext, ToolsetSpec
from llm_do.runtime.contracts import WorkerRuntimeProtocol
from llm_do.toolsets.agent import AgentToolset, agent_as_toolset
from llm_do.toolsets.approval import (
    get_toolset_approval_config,
    set_toolset_approval_config,
)


def test_agent_toolset_creation() -> None:
    """AgentToolset wraps an AgentSpec instance."""
    spec = AgentSpec(name="test", instructions="Test agent", model=TestModel())
    toolset = AgentToolset(spec=spec)

    assert toolset.spec is spec
    assert toolset.id == spec.name


def test_agent_as_toolset_spec_method() -> None:
    """agent_as_toolset() returns a ToolsetSpec factory."""
    spec = AgentSpec(name="test", instructions="Test agent", model=TestModel())
    toolset_spec = agent_as_toolset(spec)

    assert isinstance(toolset_spec, ToolsetSpec)
    toolset = toolset_spec.factory(ToolsetBuildContext(worker_name="test"))
    assert isinstance(toolset, AgentToolset)
    assert toolset.spec is spec


def test_agent_toolset_has_no_default_approval_config() -> None:
    """AgentToolset does not install approval config by default."""
    spec = AgentSpec(name="test", instructions="Test agent", model=TestModel())
    toolset = AgentToolset(spec=spec)

    config = get_toolset_approval_config(toolset)
    assert config is None


def test_agent_toolset_preserves_custom_approval() -> None:
    """AgentToolset respects existing approval config if set before creation."""
    spec = AgentSpec(name="test", instructions="Test agent", model=TestModel())
    toolset = AgentToolset(spec=spec)
    set_toolset_approval_config(toolset, {"main": {"pre_approved": False}})

    config = get_toolset_approval_config(toolset)
    assert config is not None
    assert config["main"]["pre_approved"] is False


@pytest.mark.anyio
async def test_agent_toolset_get_tools() -> None:
    """AgentToolset.get_tools() returns the agent as a callable tool."""
    spec = AgentSpec(
        name="analyzer",
        instructions="Analyze data",
        description="Data analyzer",
        model=TestModel(),
    )
    toolset = AgentToolset(spec=spec)

    mock_deps = MagicMock(spec=WorkerRuntimeProtocol)
    mock_model = TestModel()
    from pydantic_ai.usage import RunUsage
    run_ctx = RunContext(deps=mock_deps, model=mock_model, usage=RunUsage(), prompt="test")

    tools = await toolset.get_tools(run_ctx)

    assert "main" in tools
    tool = tools["main"]
    assert tool.tool_def.name == "main"
    assert tool.tool_def.description == "Data analyzer"
    assert tool.toolset is toolset


@pytest.mark.anyio
async def test_agent_toolset_truncates_long_description() -> None:
    """AgentToolset truncates descriptions longer than 200 chars."""
    long_text = "A" * 300
    spec = AgentSpec(name="test", instructions=long_text, model=TestModel())
    toolset = AgentToolset(spec=spec)

    mock_deps = MagicMock(spec=WorkerRuntimeProtocol)
    mock_model = TestModel()
    from pydantic_ai.usage import RunUsage
    run_ctx = RunContext(deps=mock_deps, model=mock_model, usage=RunUsage(), prompt="test")

    tools = await toolset.get_tools(run_ctx)
    tool = tools["main"]

    description = tool.tool_def.description
    assert description is not None
    assert description.endswith("...")
    assert description.startswith(long_text[:50])
    assert len(description) < len(long_text)


@pytest.mark.anyio
async def test_agent_toolset_call_delegates_to_call_agent() -> None:
    """AgentToolset.call_tool() delegates to deps.call_agent."""
    spec = AgentSpec(name="agent", instructions="Test", model=TestModel())
    toolset = AgentToolset(spec=spec)

    mock_deps = MagicMock(spec=WorkerRuntimeProtocol)
    mock_deps.call_agent = AsyncMock(return_value="ok")
    mock_model = TestModel()
    from pydantic_ai.usage import RunUsage
    run_ctx = RunContext(deps=mock_deps, model=mock_model, usage=RunUsage(), prompt="test")

    tools = await toolset.get_tools(run_ctx)
    tool = tools["main"]
    result = await toolset.call_tool("main", {"input": "hi"}, run_ctx, tool)

    assert result == "ok"
    mock_deps.call_agent.assert_awaited_once_with(spec, {"input": "hi"})
