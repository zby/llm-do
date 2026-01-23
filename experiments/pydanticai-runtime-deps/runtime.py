from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from approval_utils import wrap_toolsets_for_approval
from pydantic_ai import Agent, RunContext
from pydantic_ai_blocking_approval import ApprovalCallback, ApprovalConfig

from llm_do.runtime.args import PromptContent, PromptMessages, render_prompt
from llm_do.toolsets.loader import (
    ToolsetBuildContext,
    ToolsetSpec,
    instantiate_toolsets,
)


@dataclass(frozen=True)
class ToolsetResolver:
    toolset_specs: Mapping[str, Sequence[ToolsetSpec]]
    toolset_registry: Mapping[str, ToolsetSpec]

    def build_for(
        self,
        agent_name: str | None,
    ) -> list[Any]:
        if agent_name:
            specs = self.toolset_specs.get(agent_name) or []
            if specs:
                context = ToolsetBuildContext(
                    worker_name=agent_name,
                    available_toolsets=self.toolset_registry,
                )
                return instantiate_toolsets(specs, context)
        return []


@dataclass(frozen=True)
class ApprovalWrapper:
    approval_callback: ApprovalCallback | None = None
    approval_config: ApprovalConfig | None = None
    capability_map: Mapping[str, Sequence[str]] | None = None
    capability_rules: Mapping[str, str] | None = None
    capability_default: str = "needs_approval"
    approval_policy: Any | None = None

    def wrap(self, toolsets: Sequence[Any]) -> list[Any]:
        if not toolsets:
            return []
        if self.approval_callback is None:
            return list(toolsets)
        wrapped = wrap_toolsets_for_approval(
            toolsets=toolsets,
            approval_callback=self.approval_callback,
            approval_config=self.approval_config,
            capability_rules=self.capability_rules,
            capability_map=self.capability_map,
            capability_default=self.capability_default,
            approval_policy=self.approval_policy,
        )
        return list(wrapped or ())


@dataclass
class AgentRuntime:
    agents: dict[str, Agent[Any, Any]]
    base_path: Path | None = None
    toolset_specs: dict[str, Sequence[ToolsetSpec]] = field(default_factory=dict)
    toolset_registry: dict[str, ToolsetSpec] = field(default_factory=dict)
    event_stream_handler: Any | None = None
    approval_callback: ApprovalCallback | None = None
    approval_config: ApprovalConfig | None = None
    capability_map: dict[str, Sequence[str]] | None = None
    capability_rules: dict[str, str] | None = field(
        default_factory=lambda: {"proc.exec.unlisted": "blocked"}
    )
    capability_default: str = "needs_approval"
    approval_policy: Any | None = None
    max_depth: int = 5
    depth: int = 0
    _toolset_resolver: ToolsetResolver = field(init=False)
    _approval_wrapper: ApprovalWrapper = field(init=False)

    def __post_init__(self) -> None:
        self._toolset_resolver = ToolsetResolver(
            toolset_specs=self.toolset_specs,
            toolset_registry=self.toolset_registry,
        )
        self._approval_wrapper = ApprovalWrapper(
            approval_callback=self.approval_callback,
            approval_config=self.approval_config,
            capability_map=self.capability_map,
            capability_rules=self.capability_rules,
            capability_default=self.capability_default,
            approval_policy=self.approval_policy,
        )

    def spawn(self) -> "AgentRuntime":
        if self.depth >= self.max_depth:
            raise RuntimeError(
                f"max_depth exceeded: {self.depth} >= {self.max_depth}"
            )
        return replace(self, depth=self.depth + 1)

    async def call_agent(
        self,
        name: str,
        prompt: str | PromptMessages,
        *,
        ctx: RunContext["AgentRuntime"],
    ) -> Any:
        agent = self.agents.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name}")
        child = self.spawn()
        toolsets = child.toolsets_for(agent, agent_name=name)
        # Render prompt, resolving Attachment objects to BinaryContent
        messages: list[PromptContent] = [prompt] if isinstance(prompt, str) else list(prompt)
        rendered_prompt = render_prompt(messages, self.base_path)
        result = await agent.run(
            rendered_prompt,
            deps=child,
            usage=ctx.usage,
            event_stream_handler=self.event_stream_handler,
            toolsets=toolsets,
        )
        return result.output

    def _resolve_agent_name(self, agent: Agent[Any, Any]) -> str | None:
        for name, candidate in self.agents.items():
            if candidate is agent:
                return name
        return None

    def _build_toolsets(self, agent_name: str | None) -> list[Any]:
        return self._toolset_resolver.build_for(agent_name)

    def toolsets_for(
        self,
        agent: Agent[Any, Any],
        *,
        agent_name: str | None = None,
    ) -> Sequence[Any]:
        resolved_name = agent_name or self._resolve_agent_name(agent)
        toolsets = self._build_toolsets(resolved_name)
        return self._approval_wrapper.wrap(toolsets)
