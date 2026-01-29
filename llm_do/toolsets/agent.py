"""Toolset wrapper for exposing AgentSpec as a single 'main' tool."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai_blocking_approval import ApprovalResult

from ..runtime.args import Attachment, has_attachments, normalize_input
from ..runtime.contracts import AgentSpec, CallContextProtocol
from ..toolsets.validators import DictValidator
from .loader import ToolsetSpec


class _DefaultAgentToolSchema(BaseModel):
    """Default schema for agents exposed as tools."""

    input: str
    attachments: list[str] = Field(default_factory=list)


@dataclass
class AgentToolset(AbstractToolset[Any]):
    """Adapter that exposes an AgentSpec as a single tool."""

    spec: AgentSpec
    tool_name: str | None = None

    def __post_init__(self) -> None:
        if self.tool_name is None:
            self.tool_name = self.spec.name

    @property
    def id(self) -> str | None:
        return self.spec.name

    def _messages_from_args(self, tool_args: dict[str, Any]) -> list[Any] | None:
        try:
            _, messages = normalize_input(self.spec.input_model, tool_args)
            return messages
        except Exception:
            return None

    def _get_attachment_paths(self, tool_args: dict[str, Any]) -> list[str]:
        messages = self._messages_from_args(tool_args)
        if messages is not None:
            return [str(p.path) for p in messages if isinstance(p, Attachment)]
        raw_attachments = tool_args.get("attachments") or []
        return list(raw_attachments)

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: dict[str, dict[str, Any]] | None = None,
    ) -> ApprovalResult:
        tool_config = (config or {}).get(name)
        if tool_config is not None and "pre_approved" in tool_config:
            if tool_config["pre_approved"]:
                return ApprovalResult.pre_approved()
            return ApprovalResult.needs_approval()

        runtime_config = getattr(getattr(ctx, "deps", None), "config", None)
        require_all = getattr(runtime_config, "agent_calls_require_approval", False)
        require_attachments = getattr(
            runtime_config, "agent_attachments_require_approval", False
        )
        overrides = getattr(runtime_config, "agent_approval_overrides", {}) or {}
        override = overrides.get(self.spec.name)
        if override is not None:
            if override.calls_require_approval is not None:
                require_all = override.calls_require_approval
            if override.attachments_require_approval is not None:
                require_attachments = override.attachments_require_approval
        if require_all:
            return ApprovalResult.needs_approval()

        messages = self._messages_from_args(tool_args)
        has_attach = (
            has_attachments(messages)
            if messages is not None
            else bool(tool_args.get("attachments"))
        )
        if has_attach and require_attachments:
            return ApprovalResult.needs_approval()
        return ApprovalResult.pre_approved()

    def get_approval_description(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
    ) -> str:
        attachment_paths = self._get_attachment_paths(tool_args)
        if attachment_paths:
            attachment_list = ", ".join(attachment_paths)
            return f"Call agent {self.spec.name} with attachments: {attachment_list}"
        return f"Call agent {self.spec.name}"

    async def get_tools(
        self, run_ctx: RunContext[CallContextProtocol]
    ) -> dict[str, ToolsetTool[Any]]:
        tool_name = self.tool_name or self.spec.name
        desc = self.spec.description or self.spec.instructions
        desc = desc[:200] + "..." if len(desc) > 200 else desc
        schema = self.spec.input_model or _DefaultAgentToolSchema
        tool_def = ToolDefinition(
            name=tool_name,
            description=desc,
            parameters_json_schema=schema.model_json_schema(),
        )
        return {
            tool_name: ToolsetTool(
                toolset=self,
                tool_def=tool_def,
                max_retries=0,
                args_validator=DictValidator(schema),
            )
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        run_ctx: RunContext[CallContextProtocol],
        tool: ToolsetTool[Any],
    ) -> Any:
        return await run_ctx.deps.call_agent(self.spec, tool_args)


def agent_as_toolset(spec: AgentSpec, *, tool_name: str | None = None) -> ToolsetSpec:
    """Expose an AgentSpec as a ToolsetSpec with a single tool.

    The tool name defaults to spec.name so other agents can call it by name.
    """

    def factory() -> AbstractToolset[Any]:
        return AgentToolset(spec=spec, tool_name=tool_name)

    return ToolsetSpec(factory=factory)
