import pytest
from pydantic_ai.toolsets import AbstractToolset

from llm_do.ctx_runtime.approval_wrappers import ApprovalDeniedResultToolset


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
