from __future__ import annotations

from typing import Any

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import ApprovalResult

from llm_do.toolsets.loader import ToolsetRef


class _BareToolset(AbstractToolset[Any]):
    @property
    def id(self) -> str | None:
        return None

    async def get_tools(self, ctx: Any) -> dict:
        return {}

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: Any,
    ) -> Any:
        raise NotImplementedError


def test_toolset_ref_needs_approval_falls_back_to_config() -> None:
    toolset = _BareToolset()
    ref = ToolsetRef(toolset, {"safe_tool": {"pre_approved": True}})

    result = ref.needs_approval("safe_tool", {}, None, {"safe_tool": {"pre_approved": True}})

    assert isinstance(result, ApprovalResult)
    assert result.is_pre_approved
