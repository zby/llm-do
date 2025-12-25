"""Approval-related toolset wrappers."""
from __future__ import annotations

from typing import Any, Optional

from pydantic_ai.toolsets import AbstractToolset


class ApprovalDeniedResultToolset(AbstractToolset):
    """Return a tool result when a PermissionError occurs.

    This is used to keep interactive runs alive and let the model observe
    approval denials or permission failures instead of aborting the run.
    """

    def __init__(self, inner: AbstractToolset):
        self._inner = inner

    @property
    def id(self) -> Optional[str]:
        return getattr(self._inner, "id", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def get_tools(self, ctx: Any) -> dict:
        return await self._inner.get_tools(ctx)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: Any,
    ) -> Any:
        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except PermissionError as exc:
            return {
                "error": str(exc),
                "tool_name": name,
                "error_type": "permission",
            }
