import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalToolset

from llm_do.runtime import AgentSpec, FunctionEntry, Runtime
from llm_do.runtime.approval import AgentApprovalPolicy, RunApprovalPolicy
from llm_do.toolsets.filesystem import FileSystemToolset


def _approve_all(_request):
    return ApprovalDecision(approved=True)


def test_wrap_toolsets_rejects_pre_wrapped() -> None:
    policy = AgentApprovalPolicy(approval_callback=_approve_all)
    pre_wrapped = ApprovalToolset(
        inner=FileSystemToolset(config={}),
        approval_callback=_approve_all,
    )

    with pytest.raises(TypeError, match="Pre-wrapped"):
        policy.wrap_toolsets([pre_wrapped])


def test_wrap_toolsets_preserves_toolset_instances() -> None:
    policy = AgentApprovalPolicy(approval_callback=_approve_all)
    toolset = FunctionToolset()
    toolset.marker = "keep"  # type: ignore[attr-defined]

    wrapped = policy.wrap_toolsets([toolset])

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner = wrapped[0]._inner
    assert inner is toolset
    assert getattr(inner, "marker") == "keep"


@pytest.mark.anyio
async def test_agent_tool_calls_can_require_approval() -> None:
    def build_tools(_ctx) -> FunctionToolset:
        toolset = FunctionToolset()

        @toolset.tool
        def ping() -> str:
            return "pong"

        return toolset

    agent_spec = AgentSpec(
        name="child",
        instructions="Call ping.",
        model=TestModel(call_tools=["ping"], custom_output_text="done"),
        toolsets=[build_tools],
    )

    async def main(input_data, runtime) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry = FunctionEntry(name="entry", fn=main)

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(mode="reject_all"),
        agent_calls_require_approval=True,
    )

    with pytest.raises(PermissionError):
        await runtime.run_entry(entry, {"input": "go"})
