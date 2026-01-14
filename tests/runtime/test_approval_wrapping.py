import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalToolset

from llm_do.runtime import Runtime, ToolsetSpec, WorkerArgs, WorkerInput, entry
from llm_do.runtime.approval import RunApprovalPolicy, WorkerApprovalPolicy
from llm_do.runtime.worker import Worker
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
    filesystem_spec = ToolsetSpec(factory=lambda _ctx: FileSystemToolset(config={}))
    worker = Worker(
        name="child",
        instructions="Child worker",
        toolset_specs=[filesystem_spec],
        model_settings=model_settings,
    )

    wrapped = policy.wrap_toolsets([worker])

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner = wrapped[0]._inner
    assert isinstance(inner, Worker)
    assert inner.model_settings == model_settings


@pytest.mark.anyio
async def test_entry_function_exposes_its_toolsets() -> None:
    """EntryFunction exposes its toolsets via the Entry protocol."""
    def build_tools(_ctx):
        toolset = FunctionToolset()

        @toolset.tool
        def helper(input: str) -> str:
            return input

        return toolset

    toolset_spec = ToolsetSpec(factory=build_tools)

    @entry(toolsets=[toolset_spec])
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
    assert isinstance(ctx.active_toolsets[0], FunctionToolset)


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
        toolset_specs=[child.as_toolset_spec()],  # Use as_toolset_spec() for worker-as-tool
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
    child_toolset_spec = child.as_toolset_spec(
        approval_config={child.name: {"pre_approved": False}}
    )
    parent = Worker(
        name="parent",
        instructions="Parent worker",
        model=TestModel(call_tools=["child"]),
        toolset_specs=[child_toolset_spec],
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
