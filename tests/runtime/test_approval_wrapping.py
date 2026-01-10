import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalToolset

from llm_do.runtime import ToolInvocable, run_invocable
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
async def test_toolinvocable_has_no_toolsets() -> None:
    """ToolInvocable has no toolsets - it just calls a single tool directly."""
    toolset = FunctionToolset()

    @toolset.tool
    def echo(input: str) -> str:
        return input

    invocable = ToolInvocable(
        toolset=toolset,
        tool_name="echo",
    )

    result, ctx = await run_invocable(
        invocable,
        prompt="hello",
        model="test",  # Runtime needs a model even if ToolInvocable doesn't use it
        approval_policy=RunApprovalPolicy(mode="approve_all"),
    )

    assert result == "hello"
    # ToolInvocable has no toolsets - the context starts empty
    assert ctx.toolsets == ()


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
        toolsets=[child],
    )

    result, _ctx = await run_invocable(
        parent,
        prompt="trigger",
        approval_policy=RunApprovalPolicy(mode="reject_all"),
    )

    assert result is not None


@pytest.mark.anyio
async def test_nested_worker_calls_can_require_approval() -> None:
    child = Worker(
        name="child",
        instructions="Child worker",
        model=TestModel(custom_output_text="child"),
    )
    set_toolset_approval_config(child, {child.name: {"pre_approved": False}})
    parent = Worker(
        name="parent",
        instructions="Parent worker",
        model=TestModel(call_tools=["child"]),
        toolsets=[child],
    )

    with pytest.raises(PermissionError):
        await run_invocable(
            parent,
            prompt="trigger",
            approval_policy=RunApprovalPolicy(mode="reject_all"),
        )


@pytest.mark.anyio
async def test_toolinvocable_entry_call_not_approval_gated() -> None:
    """ToolInvocable entry call is not gated - it calls the tool directly."""
    toolset = FunctionToolset()

    @toolset.tool
    def echo(input: str) -> str:
        return input

    invocable = ToolInvocable(
        toolset=toolset,
        tool_name="echo",
    )

    # Even with reject_all, ToolInvocable succeeds because
    # it's a direct tool call, not an LLM-invoked tool call
    result, _ctx = await run_invocable(
        invocable,
        prompt="hello",
        model="test",  # Runtime needs a model even if ToolInvocable doesn't use it
        approval_policy=RunApprovalPolicy(mode="reject_all"),
    )

    assert result == "hello"


@pytest.mark.anyio
async def test_bulk_approval_scopes_child_tool_calls() -> None:
    toolset = FunctionToolset()

    @toolset.tool
    def tool_a(input: str) -> str:
        return f"a:{input}"

    @toolset.tool
    def tool_b(input: str) -> str:
        return f"b:{input}"

    approvals = []

    def approval_callback(request):
        approvals.append(request)
        return ApprovalDecision(approved=True)

    worker = Worker(
        name="bulk-worker",
        instructions="Call tool_a then tool_b.",
        model=TestModel(call_tools=["tool_a", "tool_b"]),
        toolsets=[toolset],
        bulk_approve_toolsets=True,
    )

    await run_invocable(
        worker,
        prompt="go",
        approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approval_callback,
        ),
    )

    assert len(approvals) == 1
