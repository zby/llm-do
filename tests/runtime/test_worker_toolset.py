"""Tests for EntryToolset adapter."""
from unittest.mock import MagicMock

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext

from llm_do.runtime import Runtime, ToolsetBuildContext, ToolsetSpec
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.contracts import CallRuntimeProtocol
from llm_do.runtime.entries import AgentEntry, EntryToolset, build_entry_tool
from llm_do.toolsets.approval import (
    get_toolset_approval_config,
    set_toolset_approval_config,
)


def test_worker_toolset_creation() -> None:
    """EntryToolset wraps an AgentEntry instance."""
    entry = AgentEntry(name="test", instructions="Test worker")
    toolset = EntryToolset(entry=entry)

    assert toolset.entry is entry
    assert toolset.id == entry.name


def test_worker_as_toolset_spec_method() -> None:
    """AgentEntry.as_toolset_spec() returns a ToolsetSpec factory."""
    entry = AgentEntry(name="test", instructions="Test worker")
    spec = entry.as_toolset_spec()

    assert isinstance(spec, ToolsetSpec)
    toolset = spec.factory(ToolsetBuildContext(worker_name="test"))
    assert isinstance(toolset, EntryToolset)
    assert toolset.entry is entry


def test_worker_toolset_has_no_default_approval_config() -> None:
    """EntryToolset does not install approval config by default."""
    entry = AgentEntry(name="test", instructions="Test worker")
    toolset = EntryToolset(entry=entry)

    config = get_toolset_approval_config(toolset)
    assert config is None


def test_worker_toolset_preserves_custom_approval() -> None:
    """EntryToolset respects existing approval config if set before creation."""
    entry = AgentEntry(name="test", instructions="Test worker")
    toolset = EntryToolset(entry=entry)
    # Override after creation
    set_toolset_approval_config(toolset, {"test": {"pre_approved": False}})

    config = get_toolset_approval_config(toolset)
    assert config is not None
    assert config["test"]["pre_approved"] is False


@pytest.mark.anyio
async def test_worker_toolset_get_tools() -> None:
    """EntryToolset.get_tools() returns the worker as a callable tool."""
    entry = AgentEntry(name="analyzer", instructions="Analyze data", description="Data analyzer")
    toolset = EntryToolset(entry=entry)

    # Create mock run context
    mock_deps = MagicMock(spec=CallRuntimeProtocol)
    mock_model = TestModel()
    from pydantic_ai.usage import RunUsage
    run_ctx = RunContext(deps=mock_deps, model=mock_model, usage=RunUsage(), prompt="test")

    tools = await toolset.get_tools(run_ctx)

    assert "analyzer" in tools
    tool = tools["analyzer"]
    assert tool.tool_def.name == "analyzer"
    assert tool.tool_def.description == "Data analyzer"
    assert tool.toolset is toolset


@pytest.mark.anyio
async def test_worker_toolset_uses_worker_name_as_tool_name() -> None:
    """EntryToolset always uses worker.name as the tool name."""
    entry = AgentEntry(name="my_worker", instructions="Instructions")
    toolset = EntryToolset(entry=entry)

    mock_deps = MagicMock(spec=CallRuntimeProtocol)
    mock_model = TestModel()
    from pydantic_ai.usage import RunUsage
    run_ctx = RunContext(deps=mock_deps, model=mock_model, usage=RunUsage(), prompt="test")

    tools = await toolset.get_tools(run_ctx)

    # Tool name is worker.name, not attribute name
    assert list(tools.keys()) == ["my_worker"]


def test_build_entry_tool_helper() -> None:
    """build_entry_tool creates consistent tool definitions."""
    entry = AgentEntry(
        name="helper_test",
        instructions="A" * 300,  # Long instructions
        description="Short description",
    )
    toolset = EntryToolset(entry=entry)

    tool = build_entry_tool(entry, toolset)

    assert tool.tool_def.name == "helper_test"
    # Uses description over instructions when available
    assert tool.tool_def.description == "Short description"
    assert tool.toolset is toolset


def test_build_entry_tool_truncates_long_description() -> None:
    """build_entry_tool truncates descriptions longer than 200 chars."""
    long_text = "A" * 300
    entry = AgentEntry(name="test", instructions=long_text)
    toolset = EntryToolset(entry=entry)

    tool = build_entry_tool(entry, toolset)

    description = tool.tool_def.description
    assert description is not None
    assert description.endswith("...")
    assert description.startswith(long_text[:50])
    assert len(description) < len(long_text)


@pytest.mark.anyio
async def test_worker_toolset_call_executes_worker() -> None:
    """EntryToolset.call_tool() executes the wrapped worker."""
    child = AgentEntry(
        name="child",
        instructions="Echo the input",
        model=TestModel(custom_output_text="echo: hello"),
    )
    parent = AgentEntry(
        name="parent",
        instructions="Call the child worker",
        model=TestModel(call_tools=["child"]),
        toolset_specs=[child.as_toolset_spec()],
    )

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    result, _ctx = await runtime.run_entry(parent, {"input": "hello"})

    assert "echo: hello" in str(result)


@pytest.mark.anyio
async def test_worker_toolset_respects_max_depth() -> None:
    """EntryToolset respects max_depth when calling wrapped workers."""
    worker = AgentEntry(
        name="recursive",
        instructions="Call yourself",
        model=TestModel(call_tools=["recursive"]),
    )
    worker.toolset_specs = [worker.as_toolset_spec()]

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
        max_depth=2,
    )

    with pytest.raises(RuntimeError, match="Max depth exceeded"):
        await runtime.run_entry(worker, {"input": "go"})


@pytest.mark.anyio
async def test_worker_toolset_preserves_worker_semantics() -> None:
    """EntryToolset preserves worker semantics like model selection."""
    child = AgentEntry(
        name="child",
        instructions="Process input",
        model=TestModel(custom_output_text="processed by child"),
        # This model is what we expect to be used
    )
    parent = AgentEntry(
        name="parent",
        instructions="Delegate to child",
        model=TestModel(call_tools=["child"]),
        toolset_specs=[child.as_toolset_spec()],
    )

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    result, _ctx = await runtime.run_entry(parent, {"input": "test"})

    # The child's specific model output should be in the result
    assert "processed by child" in str(result)
