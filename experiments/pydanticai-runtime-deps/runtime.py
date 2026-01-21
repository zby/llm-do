from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai_blocking_approval import ApprovalCallback, ApprovalConfig

from approval_utils import wrap_toolsets_for_approval


@dataclass
class AgentRuntime:
    agents: dict[str, Agent[Any, Any]]
    path_map: dict[str, Path]
    base_path: Path | None = None
    event_stream_handler: Any | None = None
    approval_callback: ApprovalCallback | None = None
    approval_config: ApprovalConfig | None = None
    capability_map: dict[str, Sequence[str]] | None = None
    capability_rules: dict[str, str] | None = None
    capability_default: str = "needs_approval"
    approval_policy: Any | None = None
    max_depth: int = 5
    depth: int = 0

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
        toolsets = child.toolsets_for(agent)
        result = await agent.run(
            prompt,
            deps=child,
            usage=ctx.usage,
            event_stream_handler=self.event_stream_handler,
            toolsets=toolsets,
        )
        return result.output

    def resolve_path(self, path: str) -> Path:
        resolved = self.path_map.get(path)
        if resolved is not None:
            return resolved
        if self.base_path is not None:
            return (self.base_path / path).expanduser().resolve()
        return Path(path).expanduser().resolve()

    def load_binary(self, path: str) -> BinaryContent:
        return BinaryContent.from_path(self.resolve_path(path))

    def toolsets_for(self, agent: Agent[Any, Any]) -> Sequence[Any] | None:
        return wrap_toolsets_for_approval(
            toolsets=agent.toolsets,
            approval_callback=self.approval_callback,
            approval_config=self.approval_config,
            capability_rules=self.capability_rules,
            capability_map=self.capability_map,
            capability_default=self.capability_default,
            approval_policy=self.approval_policy,
        )


def build_path_map(mapping: Mapping[str, Path]) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for key, value in mapping.items():
        resolved[key] = value.resolve()
    return resolved
