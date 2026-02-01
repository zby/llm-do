"""Dynamic agent creation and invocation toolset."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai_blocking_approval import (
    ApprovalConfig,
    ApprovalResult,
    needs_approval_from_config,
)

from ..models import select_model_with_id
from ..runtime.agent_file import build_agent_definition, load_agent_file_parts
from ..runtime.contracts import AgentSpec, CallContextProtocol
from ..toolsets.loader import resolve_toolset_specs
from ..toolsets.validators import DictValidator

_DEFAULT_GENERATED_DIR = Path("/tmp/llm-do/generated")
_AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class AgentCreateArgs(BaseModel):
    """Arguments for agent_create."""

    name: str = Field(description="Name for the new agent")
    instructions: str = Field(description="Instruction prompt for the new agent")
    description: str = Field(description="Short description of the new agent")
    model: str | None = Field(
        default=None,
        description="Optional model override (defaults to LLM_DO_MODEL)",
    )
    toolsets: list[str] = Field(
        default_factory=list,
        description="Toolset names to enable for the new agent",
    )


class AgentCallArgs(BaseModel):
    """Arguments for agent_call."""

    agent: str = Field(description="Name of the dynamic agent to call")
    input: str = Field(description="Input text to pass to the agent")
    attachments: list[str] = Field(
        default_factory=list,
        description="Attachment paths to include with the call",
    )


@dataclass
class DynamicAgentsToolset(AbstractToolset[Any]):
    """Toolset exposing agent_create/agent_call for dynamic agents."""

    _max_retries: int = 0

    @property
    def id(self) -> str | None:
        return None

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: ApprovalConfig | None = None,
    ) -> ApprovalResult:
        base = needs_approval_from_config(name, config)
        if base.is_blocked or base.is_pre_approved:
            return base

        if name == "agent_create":
            return ApprovalResult.needs_approval()

        if name == "agent_call":
            runtime_config = getattr(getattr(ctx, "deps", None), "config", None)
            require_all = getattr(runtime_config, "agent_calls_require_approval", False)
            require_attachments = getattr(
                runtime_config, "agent_attachments_require_approval", False
            )
            overrides = getattr(runtime_config, "agent_approval_overrides", {}) or {}
            override = overrides.get(tool_args.get("agent", ""))
            if override is not None:
                if override.calls_require_approval is not None:
                    require_all = override.calls_require_approval
                if override.attachments_require_approval is not None:
                    require_attachments = override.attachments_require_approval
            if require_all:
                return ApprovalResult.needs_approval()
            if tool_args.get("attachments") and require_attachments:
                return ApprovalResult.needs_approval()
            return ApprovalResult.pre_approved()

        return ApprovalResult.needs_approval()

    def get_approval_description(
        self, name: str, tool_args: dict[str, Any], ctx: Any
    ) -> str:
        if name == "agent_create":
            toolsets = tool_args.get("toolsets") or []
            model = tool_args.get("model")
            suffix = []
            if toolsets:
                suffix.append(f"toolsets={toolsets}")
            if model:
                suffix.append(f"model={model}")
            details = f" ({', '.join(suffix)})" if suffix else ""
            return f"Create agent {tool_args.get('name', '')}{details}"
        if name == "agent_call":
            attachments = tool_args.get("attachments") or []
            if attachments:
                attachment_list = ", ".join(attachments)
                return f"Call agent {tool_args.get('agent', '')} with attachments: {attachment_list}"
            return f"Call agent {tool_args.get('agent', '')}"
        return f"{name}({tool_args})"

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        return {
            "agent_create": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="agent_create",
                    description="Create a new agent definition for this session.",
                    parameters_json_schema=AgentCreateArgs.model_json_schema(),
                    sequential=True,
                ),
                max_retries=self._max_retries,
                args_validator=DictValidator(AgentCreateArgs),
            ),
            "agent_call": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="agent_call",
                    description="Call a dynamically created agent by name.",
                    parameters_json_schema=AgentCallArgs.model_json_schema(),
                    sequential=True,
                ),
                max_retries=self._max_retries,
                args_validator=DictValidator(AgentCallArgs),
            ),
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        call_ctx = getattr(ctx, "deps", None)
        if call_ctx is None:
            raise TypeError("dynamic_agents tools require CallContext deps")

        if name == "agent_create":
            create_args = AgentCreateArgs.model_validate(tool_args)
            return self._agent_create(call_ctx, create_args)
        if name == "agent_call":
            call_args = AgentCallArgs.model_validate(tool_args)
            return await self._agent_call(call_ctx, call_args)
        raise ValueError(f"Unknown tool: {name}")

    def _agent_create(
        self,
        ctx: CallContextProtocol,
        args: AgentCreateArgs,
    ) -> str:
        name = args.name.strip()
        if not name:
            raise ValueError("agent_create requires a non-empty name")
        if not _AGENT_NAME_PATTERN.match(name):
            raise ValueError(
                "Agent name must contain only letters, numbers, '_' or '-'"
            )
        if name in ctx.dynamic_agents:
            raise ValueError(f"Dynamic agent '{name}' already exists")
        if name in ctx.agent_registry:
            raise ValueError(f"Agent name '{name}' conflicts with a registered agent")

        instructions = args.instructions.strip()
        if not instructions:
            raise ValueError("agent_create requires non-empty instructions")

        generated_dir = self._resolve_generated_dir(ctx)
        generated_dir.mkdir(parents=True, exist_ok=True)
        agent_path = generated_dir / f"{name}.agent"
        if agent_path.exists():
            raise FileExistsError(f"Agent file already exists: {agent_path}")

        frontmatter = self._render_frontmatter(
            name=name,
            description=args.description,
            model=args.model,
            toolsets=args.toolsets,
        )
        content = f"{frontmatter}\n\n{instructions}\n"
        agent_path.write_text(content, encoding="utf-8")

        try:
            parsed_frontmatter, parsed_instructions = load_agent_file_parts(agent_path)
            agent_def = build_agent_definition(
                parsed_frontmatter,
                parsed_instructions,
            )
            toolset_specs = []
            if agent_def.toolsets:
                available_toolsets = ctx.toolset_registry
                if not available_toolsets:
                    raise ValueError(
                        "Toolset registry unavailable; cannot validate toolsets."
                    )
                toolset_specs = resolve_toolset_specs(
                    agent_def.toolsets,
                    available_toolsets=available_toolsets,
                    agent_name=agent_def.name,
                )
            selection = select_model_with_id(
                agent_model=agent_def.model,
                compatible_models=agent_def.compatible_models,
                agent_name=agent_def.name,
            )
            spec = AgentSpec(
                name=agent_def.name,
                instructions=agent_def.instructions,
                description=agent_def.description,
                model=selection.model,
                model_id=selection.model_id,
                toolset_specs=toolset_specs,
            )
        except Exception:
            try:
                agent_path.unlink()
            except FileNotFoundError:
                pass
            raise

        ctx.dynamic_agents[name] = spec
        return name

    async def _agent_call(
        self,
        ctx: CallContextProtocol,
        args: AgentCallArgs,
    ) -> Any:
        name = args.agent.strip()
        if not name:
            raise ValueError("agent_call requires a non-empty agent name")
        try:
            spec = ctx.dynamic_agents[name]
        except KeyError as exc:
            available = sorted(ctx.dynamic_agents.keys())
            raise ValueError(
                f"Dynamic agent '{name}' not found. Available: {available}"
            ) from exc

        input_data: dict[str, Any] = {"input": args.input}
        if args.attachments:
            input_data["attachments"] = list(args.attachments)
        return await ctx.call_agent(spec, input_data)

    def _resolve_generated_dir(self, ctx: CallContextProtocol) -> Path:
        value = getattr(ctx.config, "generated_agents_dir", None)
        if value is None:
            return _DEFAULT_GENERATED_DIR
        if isinstance(value, Path):
            return value
        return Path(value).expanduser().resolve()

    def _render_frontmatter(
        self,
        *,
        name: str,
        description: str,
        model: str | None,
        toolsets: list[str],
    ) -> str:
        lines = ["---"]
        lines.append(f"name: {json.dumps(name)}")
        if description:
            lines.append(f"description: {json.dumps(description)}")
        if model:
            lines.append(f"model: {json.dumps(model)}")
        if toolsets:
            lines.append("toolsets:")
            for toolset in toolsets:
                lines.append(f"  - {json.dumps(toolset)}")
        lines.append("---")
        return "\n".join(lines)
