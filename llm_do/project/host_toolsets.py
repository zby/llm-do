"""Host-owned helpers for assembling project-layer toolsets."""
from __future__ import annotations

from pathlib import Path

from ..runtime.contracts import AgentSpec
from ..runtime.tooling import ToolsetDef
from ..toolsets.agent import agent_as_toolset
from ..toolsets.builtins import build_builtin_toolsets
from .registry import AgentToolsetFactory


def build_host_toolsets(
    cwd: Path,
    project_root: Path,
) -> dict[str, ToolsetDef]:
    return build_builtin_toolsets(cwd, project_root)


def build_agent_toolset_factory() -> AgentToolsetFactory:
    def factory(agent_name: str, spec: AgentSpec) -> ToolsetDef:
        return agent_as_toolset(spec, tool_name=agent_name)

    return factory
