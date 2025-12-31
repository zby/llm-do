import pytest
from pydantic_ai.toolsets import AbstractToolset

from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

from llm_do.ctx_runtime.approval_wrappers import (
    ApprovalDeniedResultToolset,
    make_headless_approval_callback,
    make_tui_approval_callback,
)


class _FailingToolset(AbstractToolset):
    @property
    def id(self):
        return None

    async def get_tools(self, ctx):
        return {}

    async def call_tool(self, name, tool_args, ctx, tool):
        raise PermissionError("Denied by user")


class _OkToolset(AbstractToolset):
    @property
    def id(self):
        return None

    async def get_tools(self, ctx):
        return {}

    async def call_tool(self, name, tool_args, ctx, tool):
        return {"ok": True}


@pytest.mark.anyio
async def test_permission_error_returns_payload():
    wrapper = ApprovalDeniedResultToolset(_FailingToolset())
    result = await wrapper.call_tool("tool", {"x": 1}, None, None)
    assert result["error_type"] == "permission"
    assert "Denied by user" in result["error"]


@pytest.mark.anyio
async def test_non_permission_errors_passthrough():
    wrapper = ApprovalDeniedResultToolset(_OkToolset())
    result = await wrapper.call_tool("tool", {"x": 1}, None, None)
    assert result == {"ok": True}


def test_make_headless_approval_callback_approve_all():
    cb = make_headless_approval_callback(approve_all=True, reject_all=False)
    decision = cb(ApprovalRequest(tool_name="t", tool_args={}, description="x"))
    assert decision == ApprovalDecision(approved=True)


def test_make_headless_approval_callback_reject_all():
    cb = make_headless_approval_callback(approve_all=False, reject_all=True)
    decision = cb(ApprovalRequest(tool_name="t", tool_args={}, description="x"))
    assert decision.approved is False
    assert decision.note == "--reject-all"


def test_make_headless_approval_callback_default_denies():
    cb = make_headless_approval_callback(
        approve_all=False,
        reject_all=False,
        deny_note="nope",
    )
    decision = cb(ApprovalRequest(tool_name="t", tool_args={}, description="x"))
    assert decision.approved is False
    assert decision.note == "nope"


def test_make_headless_approval_callback_conflicting_flags():
    with pytest.raises(ValueError, match="approve_all"):
        make_headless_approval_callback(approve_all=True, reject_all=True)


@pytest.mark.anyio
async def test_make_tui_approval_callback_caches_session_approvals():
    calls: list[ApprovalRequest] = []

    async def prompt_user(request: ApprovalRequest) -> ApprovalDecision:
        calls.append(request)
        return ApprovalDecision(approved=True, remember="session")

    cb = make_tui_approval_callback(prompt_user, approve_all=False, reject_all=False)

    req1 = ApprovalRequest(tool_name="write_file", tool_args={"path": "a"}, description="first")
    req2 = ApprovalRequest(tool_name="write_file", tool_args={"path": "a"}, description="second")

    decision1 = await cb(req1)
    decision2 = await cb(req2)

    assert decision1.approved is True
    assert decision2.approved is True
    assert len(calls) == 1


@pytest.mark.anyio
async def test_make_tui_approval_callback_does_not_cache_one_off_approvals():
    calls: list[ApprovalRequest] = []

    async def prompt_user(request: ApprovalRequest) -> ApprovalDecision:
        calls.append(request)
        return ApprovalDecision(approved=True)  # remember="none"

    cb = make_tui_approval_callback(prompt_user, approve_all=False, reject_all=False)

    req = ApprovalRequest(tool_name="read_file", tool_args={"path": "a"}, description="x")
    await cb(req)
    await cb(req)

    assert len(calls) == 2


@pytest.mark.anyio
async def test_make_tui_approval_callback_approve_all_short_circuits():
    async def prompt_user(_request: ApprovalRequest) -> ApprovalDecision:
        raise AssertionError("prompt_user should not be called")

    cb = make_tui_approval_callback(prompt_user, approve_all=True, reject_all=False)
    decision = await cb(ApprovalRequest(tool_name="t", tool_args={}, description="x"))
    assert decision.approved is True


@pytest.mark.anyio
async def test_make_tui_approval_callback_reject_all_short_circuits():
    async def prompt_user(_request: ApprovalRequest) -> ApprovalDecision:
        raise AssertionError("prompt_user should not be called")

    cb = make_tui_approval_callback(prompt_user, approve_all=False, reject_all=True)
    decision = await cb(ApprovalRequest(tool_name="t", tool_args={}, description="x"))
    assert decision.approved is False
    assert decision.note == "--reject-all"
