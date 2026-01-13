import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalToolset

from llm_do.runtime import Runtime, WorkerArgs, WorkerInput, entry
from llm_do.runtime.approval import RunApprovalPolicy, WorkerApprovalPolicy
from llm_do.runtime.worker import Worker
from llm_do.toolsets.approval import set_toolset_approval_config
from llm_do.toolsets.filesystem import FileSystemToolset

# TestModel is used in test_nested_worker_calls_are_approval_gated


def _approve_all(_request):
    return ApprovalDecision(approved=True)


def test_wrap_toolsets_rejects_pre_wrapped() -> None:
    policy = WorkerApprovalPolicy(approval_callback=_approve_all)
    pre_wrapped = ApprovalToolset(
        inner=FileSystemToolset(config={}),
        approval_callback=_approve_all,
    )

    with pytest.raises(TypeError, match="Pre-wrapped"):
        policy.wrap_toolsets([pre_wrapped])


def test_wrap_toolsets_preserves_worker_fields() -> None:
    policy = WorkerApprovalPolicy(approval_callback=_approve_all)
    model_settings = ModelSettings(temperature=0.2)
    worker = Worker(
        name="child",
        instructions="Child worker",
        toolsets=[FileSystemToolset(config={})],
        model_settings=model_settings,
    )

    wrapped = policy.wrap_toolsets([worker])

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner = wrapped[0]._inner
    assert isinstance(inner, Worker)
    assert inner.model_settings == model_settings


def test_wrap_toolsets_is_shallow() -> None:
    policy = WorkerApprovalPolicy(approval_callback=_approve_all)
    worker_a = Worker(name="worker_a", instructions="A")
    worker_b = Worker(name="worker_b", instructions="B", toolsets=[FileSystemToolset(config={})])
    worker_a.toolsets = [worker_b]

    wrapped = policy.wrap_toolsets([worker_a])

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner_a = wrapped[0]._inner
    assert inner_a is worker_a
    assert inner_a.toolsets[0] is worker_b
    assert not isinstance(worker_b.toolsets[0], ApprovalToolset)


def test_wrap_toolsets_handles_cycles() -> None:
    policy = WorkerApprovalPolicy(approval_callback=_approve_all)
    worker_a = Worker(name="worker_a", instructions="A")
    worker_b = Worker(name="worker_b", instructions="B")
    worker_a.toolsets = [worker_b]
    worker_b.toolsets = [worker_a]

    wrapped = policy.wrap_toolsets([worker_a])

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner_a = wrapped[0]._inner
    assert inner_a is worker_a
    assert inner_a.toolsets[0] is worker_b
    assert worker_b.toolsets[0] is worker_a
    assert not isinstance(worker_b.toolsets[0], ApprovalToolset)


@pytest.mark.anyio
async def test_entry_function_exposes_its_toolsets() -> None:
    """EntryFunction exposes its toolsets via the Entry protocol."""
    toolset = FunctionToolset()

    @toolset.tool
    def helper(input: str) -> str:
        return input

    @entry(toolsets=[toolset])
    async def echo(args: WorkerArgs, runtime_ctx) -> str:
        # args is WorkerInput with .input attribute
        return args.prompt_spec().text

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    result, ctx = await runtime.run_entry(
        echo,
        {"input": "hello"},
        model="test",
    )

    assert result == "hello"
    # ToolInvocable exposes its toolset via the Entry protocol
    assert len(ctx.active_toolsets) == 1
    assert ctx.active_toolsets[0] is toolset


@pytest.mark.anyio
async def test_nested_worker_calls_bypass_approval_by_default() -> None:
    child = Worker(
        name="child",
        instructions="Child worker",
        model=TestModel(custom_output_text="child"),
    )
    parent = Worker(
        name="parent",
        instructions="Parent worker",
        model=TestModel(call_tools=["child"]),
        toolsets=[child.as_toolset()],  # Use as_toolset() for explicit worker-as-tool
    )

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="reject_all"))
    result, _ctx = await runtime.run_entry(parent, WorkerInput(input="trigger"))

    assert result is not None


@pytest.mark.anyio
async def test_nested_worker_calls_can_require_approval() -> None:
    child = Worker(
        name="child",
        instructions="Child worker",
        model=TestModel(custom_output_text="child"),
    )
    child_toolset = child.as_toolset()  # Use as_toolset() for explicit worker-as-tool
    set_toolset_approval_config(child_toolset, {child.name: {"pre_approved": False}})
    parent = Worker(
        name="parent",
        instructions="Parent worker",
        model=TestModel(call_tools=["child"]),
        toolsets=[child_toolset],
    )

    with pytest.raises(PermissionError):
        runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="reject_all"))
        await runtime.run_entry(parent, WorkerInput(input="trigger"))


@pytest.mark.anyio
async def test_entry_function_call_not_approval_gated() -> None:
    """EntryFunction call is not gated - it's a direct call, not LLM-invoked."""

    @entry()
    async def echo(args: WorkerArgs, runtime_ctx) -> str:
        return args.prompt_spec().text

    # Even with reject_all, EntryFunction succeeds because
    # it's a direct call, not an LLM-invoked tool call
    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="reject_all"))
    result, _ctx = await runtime.run_entry(
        echo,
        {"input": "hello"},
        model="test",
    )

    assert result == "hello"

