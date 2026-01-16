"""Tests for WorkerToolset adapter."""
from unittest.mock import MagicMock

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext

from llm_do.runtime import Runtime, ToolsetBuildContext, ToolsetSpec, WorkerInput
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.contracts import WorkerRuntimeProtocol
from llm_do.runtime.worker import Worker, WorkerToolset, build_worker_tool
from llm_do.toolsets.approval import (
    get_toolset_approval_config,
    set_toolset_approval_config,
)


def test_worker_toolset_creation() -> None:
    """WorkerToolset wraps a Worker instance."""
    worker = Worker(name="test", instructions="Test worker")
    toolset = WorkerToolset(worker=worker)

    assert toolset.worker is worker
    assert toolset.id == worker.name


def test_worker_as_toolset_spec_method() -> None:
    """Worker.as_toolset_spec() returns a ToolsetSpec factory."""
    worker = Worker(name="test", instructions="Test worker")
    spec = worker.as_toolset_spec()

    assert isinstance(spec, ToolsetSpec)
    toolset = spec.factory(ToolsetBuildContext(worker_name="test"))
    assert isinstance(toolset, WorkerToolset)
    assert toolset.worker is worker


def test_worker_toolset_has_no_default_approval_config() -> None:
    """WorkerToolset does not install approval config by default."""
    worker = Worker(name="test", instructions="Test worker")
    toolset = WorkerToolset(worker=worker)

    config = get_toolset_approval_config(toolset)
    assert config is None


def test_worker_toolset_preserves_custom_approval() -> None:
    """WorkerToolset respects existing approval config if set before creation."""
    worker = Worker(name="test", instructions="Test worker")
    toolset = WorkerToolset(worker=worker)
    # Override after creation
    set_toolset_approval_config(toolset, {"test": {"pre_approved": False}})

    config = get_toolset_approval_config(toolset)
    assert config["test"]["pre_approved"] is False


@pytest.mark.anyio
async def test_worker_toolset_get_tools() -> None:
    """WorkerToolset.get_tools() returns the worker as a callable tool."""
    worker = Worker(name="analyzer", instructions="Analyze data", description="Data analyzer")
    toolset = WorkerToolset(worker=worker)

    # Create mock run context
    mock_deps = MagicMock(spec=WorkerRuntimeProtocol)
    run_ctx = RunContext(deps=mock_deps, model=None, usage=None, prompt="test")

    tools = await toolset.get_tools(run_ctx)

    assert "analyzer" in tools
    tool = tools["analyzer"]
    assert tool.tool_def.name == "analyzer"
    assert tool.tool_def.description == "Data analyzer"
    assert tool.toolset is toolset


@pytest.mark.anyio
async def test_worker_toolset_uses_worker_name_as_tool_name() -> None:
    """WorkerToolset always uses worker.name as the tool name."""
    worker = Worker(name="my_worker", instructions="Instructions")
    toolset = WorkerToolset(worker=worker)

    mock_deps = MagicMock(spec=WorkerRuntimeProtocol)
    run_ctx = RunContext(deps=mock_deps, model=None, usage=None, prompt="test")

    tools = await toolset.get_tools(run_ctx)

    # Tool name is worker.name, not attribute name
    assert list(tools.keys()) == ["my_worker"]


def test_build_worker_tool_helper() -> None:
    """build_worker_tool creates consistent tool definitions."""
    worker = Worker(
        name="helper_test",
        instructions="A" * 300,  # Long instructions
        description="Short description",
    )
    toolset = WorkerToolset(worker=worker)

    tool = build_worker_tool(worker, toolset)

    assert tool.tool_def.name == "helper_test"
    # Uses description over instructions when available
    assert tool.tool_def.description == "Short description"
    assert tool.toolset is toolset


def test_build_worker_tool_truncates_long_description() -> None:
    """build_worker_tool truncates descriptions longer than 200 chars."""
    long_text = "A" * 300
    worker = Worker(name="test", instructions=long_text)
    toolset = WorkerToolset(worker=worker)

    tool = build_worker_tool(worker, toolset)

    description = tool.tool_def.description
    assert description.endswith("...")
    assert description.startswith(long_text[:50])
    assert len(description) < len(long_text)


@pytest.mark.anyio
async def test_worker_toolset_call_executes_worker() -> None:
    """WorkerToolset.call_tool() executes the wrapped worker."""
    child = Worker(
        name="child",
        instructions="Echo the input",
        model=TestModel(custom_output_text="echo: hello"),
    )
    parent = Worker(
        name="parent",
        instructions="Call the child worker",
        model=TestModel(call_tools=["child"]),
        toolset_specs=[child.as_toolset_spec()],
    )

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    result, _ctx = await runtime.run_entry(parent, WorkerInput(input="hello"))

    assert "echo: hello" in str(result)


@pytest.mark.anyio
async def test_worker_toolset_respects_max_depth() -> None:
    """WorkerToolset respects max_depth when calling wrapped workers."""
    worker = Worker(
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
        await runtime.run_entry(worker, WorkerInput(input="go"))


@pytest.mark.anyio
async def test_worker_toolset_preserves_worker_semantics() -> None:
    """WorkerToolset preserves worker semantics like model selection."""
    child = Worker(
        name="child",
        instructions="Process input",
        model=TestModel(custom_output_text="processed by child"),
        # This model is what we expect to be used
    )
    parent = Worker(
        name="parent",
        instructions="Delegate to child",
        model=TestModel(call_tools=["child"]),
        toolset_specs=[child.as_toolset_spec()],
    )

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    result, _ctx = await runtime.run_entry(parent, WorkerInput(input="test"))

    # The child's specific model output should be in the result
    assert "processed by child" in str(result)
