from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai_blocking_approval import ApprovalCallback, ApprovalConfig

from approval_utils import wrap_toolsets_for_approval
from llm_do.toolsets.loader import ToolsetBuildContext, ToolsetSpec, instantiate_toolsets


@dataclass(frozen=True)
class PathResolver:
    path_map: Mapping[str, Path]
    base_path: Path | None = None

    def resolve(self, path: str) -> Path:
        resolved = self.path_map.get(path)
        if resolved is not None:
            return resolved
        if self.base_path is not None:
            return (self.base_path / path).expanduser().resolve()
        return Path(path).expanduser().resolve()

    def load_binary(self, path: str) -> BinaryContent:
        return BinaryContent.from_path(self.resolve(path))


@dataclass(frozen=True)
class ToolsetResolver:
    toolset_specs: Mapping[str, Sequence[ToolsetSpec]]
    toolset_registry: Mapping[str, ToolsetSpec]

    def build_for(
        self,
        agent_name: str | None,
        fallback_toolsets: Sequence[Any] | None,
    ) -> list[Any]:
        if agent_name:
            specs = self.toolset_specs.get(agent_name) or []
            if specs:
                context = ToolsetBuildContext(
                    worker_name=agent_name,
                    available_toolsets=self.toolset_registry,
                )
                return instantiate_toolsets(specs, context)
        return list(fallback_toolsets or ())


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
    path_map: dict[str, Path]
    toolset_specs: dict[str, Sequence[ToolsetSpec]] = field(default_factory=dict)
    toolset_registry: dict[str, ToolsetSpec] = field(default_factory=dict)
    base_path: Path | None = None
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
    _path_resolver: PathResolver = field(init=False)
    _toolset_resolver: ToolsetResolver = field(init=False)
    _approval_wrapper: ApprovalWrapper = field(init=False)

    def __post_init__(self) -> None:
        self._path_resolver = PathResolver(
            path_map=self.path_map,
            base_path=self.base_path,
        )
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
        prompt: str | Sequence[Any],
        *,
        ctx: RunContext["AgentRuntime"],
    ) -> Any:
        agent = self.agents.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name}")
        child = self.spawn()
        toolsets = child.toolsets_for(agent, agent_name=name)
        result = await agent.run(
            prompt,
            deps=child,
            usage=ctx.usage,
            event_stream_handler=self.event_stream_handler,
            toolsets=toolsets,
        )
        return result.output

    def resolve_path(self, path: str) -> Path:
        return self._path_resolver.resolve(path)

    def load_binary(self, path: str) -> BinaryContent:
        return self._path_resolver.load_binary(path)

    def _resolve_agent_name(self, agent: Agent[Any, Any]) -> str | None:
        for name, candidate in self.agents.items():
            if candidate is agent:
                return name
        return None

    def _build_toolsets(
        self,
        agent: Agent[Any, Any],
        *,
        agent_name: str | None,
    ) -> list[Any]:
        return self._toolset_resolver.build_for(
            agent_name,
            agent.toolsets,
        )

    def toolsets_for(
        self,
        agent: Agent[Any, Any],
        *,
        agent_name: str | None = None,
    ) -> Sequence[Any]:
        resolved_name = agent_name or self._resolve_agent_name(agent)
        toolsets = self._build_toolsets(agent, agent_name=resolved_name)
        return self._approval_wrapper.wrap(toolsets)


def build_path_map(mapping: Mapping[str, Path]) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for key, value in mapping.items():
        resolved[key] = value.resolve()
    return resolved
