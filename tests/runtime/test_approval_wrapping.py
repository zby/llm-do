from typing import Any

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalToolset

from llm_do.runtime import (
    AgentEntry,
    EntryToolset,
    Runtime,
    ToolsetSpec,
    WorkerArgs,
    entry,
)
from llm_do.runtime.approval import RunApprovalPolicy, WorkerApprovalPolicy
from llm_do.toolsets.approval import set_toolset_approval_config
from llm_do.toolsets.filesystem import FileSystemToolset


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


def test_wrap_toolsets_preserves_entry_toolsets() -> None:
    policy = WorkerApprovalPolicy(approval_callback=_approve_all)
    model_settings = ModelSettings(temperature=0.2)
    filesystem_spec = ToolsetSpec(factory=lambda _ctx: FileSystemToolset(config={}))
    entry_instance = AgentEntry(
        name="child",
        instructions="Child entry",
        toolset_specs=[filesystem_spec],
        model_settings=model_settings,
        model=TestModel(),
    )

    wrapped = policy.wrap_toolsets([EntryToolset(entry=entry_instance)])

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner = wrapped[0]._inner
    assert isinstance(inner, EntryToolset)
    assert inner.entry.model_settings == model_settings


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
    async def echo(messages, _scope) -> str:
        return messages[0] if messages else ""

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="approve_all"))
    result, ctx = await runtime.run_entry(
        echo,
        {"input": "hello"},
    )

    assert result == "hello"
    assert len(ctx.frame.config.active_toolsets) == 1
    assert isinstance(ctx.frame.config.active_toolsets[0], ApprovalToolset)


@pytest.mark.anyio
async def test_nested_entry_calls_bypass_approval_by_default() -> None:
    child = AgentEntry(
        name="child",
        instructions="Child entry",
        model=TestModel(custom_output_text="child"),
    )
    parent = AgentEntry(
        name="parent",
        instructions="Parent entry",
        model=TestModel(call_tools=["child"]),
        toolset_specs=[child.as_toolset_spec()],
    )

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="reject_all"))
    result, _ctx = await runtime.run_entry(parent, {"input": "trigger"})

    assert result is not None


@pytest.mark.anyio
async def test_nested_entry_calls_can_require_approval() -> None:
    child = AgentEntry(
        name="child",
        instructions="Child entry",
        model=TestModel(custom_output_text="child"),
    )
    child_toolset_spec = child.as_toolset_spec(
        approval_config={child.name: {"pre_approved": False}}
    )
    parent = AgentEntry(
        name="parent",
        instructions="Parent entry",
        model=TestModel(call_tools=["child"]),
        toolset_specs=[child_toolset_spec],
    )

    with pytest.raises(PermissionError):
        runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="reject_all"))
        await runtime.run_entry(parent, {"input": "trigger"})


@pytest.mark.anyio
async def test_entry_call_with_attachments_does_not_require_approval_by_default(
    tmp_path,
) -> None:
    calls = []
    attachment_path = tmp_path / "deck.pdf"
    attachment_path.write_text("data")

    def approval_callback(request):
        calls.append(request)
        return ApprovalDecision(approved=False, note="deny")

    child = AgentEntry(
        name="child",
        instructions="Child entry",
        model=TestModel(custom_output_text="child"),
    )

    @entry(toolsets=[child.as_toolset_spec()])
    async def parent(args: WorkerArgs, scope) -> str:
        return await scope.call_tool(
            "child",
            {
                "input": "analyze",
                "attachments": [str(attachment_path)],
            },
        )

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approval_callback,
        )
    )
    result, _ctx = await runtime.run_entry(parent, {"input": "run"})

    assert result is not None
    assert calls == []


@pytest.mark.anyio
async def test_entry_call_requires_approval_with_attachments(tmp_path) -> None:
    calls = []
    attachment_path = tmp_path / "deck.pdf"
    attachment_path.write_text("data")

    def approval_callback(request):
        calls.append(request)
        return ApprovalDecision(approved=False, note="deny")

    child = AgentEntry(
        name="child",
        instructions="Child entry",
        model=TestModel(custom_output_text="child"),
    )

    @entry(toolsets=[child.as_toolset_spec()])
    async def parent(args: WorkerArgs, scope) -> str:
        return await scope.call_tool(
            "child",
            {
                "input": "analyze",
                "attachments": [str(attachment_path)],
            },
        )

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approval_callback,
        ),
        worker_attachments_require_approval=True,
    )
    with pytest.raises(PermissionError):
        await runtime.run_entry(parent, {"input": "run"})

    assert len(calls) == 1
    assert str(attachment_path) in calls[0].description


@pytest.mark.anyio
async def test_entry_approval_override_requires_approval_without_attachments() -> None:
    calls = []

    def approval_callback(request):
        calls.append(request)
        return ApprovalDecision(approved=False, note="deny")

    child = AgentEntry(
        name="child",
        instructions="Child entry",
        model=TestModel(custom_output_text="child"),
    )

    @entry(toolsets=[child.as_toolset_spec()])
    async def parent(args: WorkerArgs, scope) -> str:
        return await scope.call_tool(
            "child",
            {
                "input": "analyze",
            },
        )

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approval_callback,
        ),
        worker_approval_overrides={
            "child": {"calls_require_approval": True},
        },
    )
    with pytest.raises(PermissionError):
        await runtime.run_entry(parent, {"input": "run"})

    assert len(calls) == 1


@pytest.mark.anyio
async def test_entry_approval_override_requires_approval_for_attachments(
    tmp_path,
) -> None:
    calls = []
    attachment_path = tmp_path / "deck.pdf"
    attachment_path.write_text("data")

    def approval_callback(request):
        calls.append(request)
        return ApprovalDecision(approved=False, note="deny")

    child = AgentEntry(
        name="child",
        instructions="Child entry",
        model=TestModel(custom_output_text="child"),
    )

    @entry(toolsets=[child.as_toolset_spec()])
    async def parent(args: WorkerArgs, scope) -> str:
        return await scope.call_tool(
            "child",
            {
                "input": "analyze",
                "attachments": [str(attachment_path)],
            },
        )

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approval_callback,
        ),
        worker_approval_overrides={
            "child": {"attachments_require_approval": True},
        },
    )
    with pytest.raises(PermissionError):
        await runtime.run_entry(parent, {"input": "run"})

    assert len(calls) == 1
    assert str(attachment_path) in calls[0].description


@pytest.mark.anyio
async def test_entry_function_call_not_approval_gated() -> None:
    """EntryFunction itself is not gated; tool calls inside are policy-gated."""

    @entry()
    async def echo(messages, _scope) -> str:
        return messages[0] if messages else ""

    runtime = Runtime(run_approval_policy=RunApprovalPolicy(mode="reject_all"))
    result, _ctx = await runtime.run_entry(
        echo,
        {"input": "hello"},
    )

    assert result == "hello"


@pytest.mark.anyio
async def test_entry_tool_calls_respect_return_permission_errors() -> None:
    """Entry tool calls should honor return_permission_errors like agents."""
    def build_tools(_ctx):
        toolset = FunctionToolset()

        @toolset.tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        set_toolset_approval_config(toolset, {"greet": {"pre_approved": False}})
        return toolset

    toolset_spec = ToolsetSpec(factory=build_tools)

    @entry(toolsets=[toolset_spec])
    async def call_tool(args: WorkerArgs, scope) -> Any:
        return await scope.call_tool("greet", {"name": "World"})

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(
            mode="reject_all",
            return_permission_errors=True,
        )
    )
    result, _ctx = await runtime.run_entry(
        call_tool,
        {"input": "hello"},
    )

    assert isinstance(result, dict)
    assert result.get("error_type") == "permission"
