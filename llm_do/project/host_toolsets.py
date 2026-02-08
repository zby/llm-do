"""Host-owned helpers for assembling project-layer toolsets."""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from ..runtime.contracts import AgentSpec
from ..runtime.tooling import ToolsetDef
from ..toolsets.agent import agent_as_toolset
from ..toolsets.builtins import build_builtin_toolsets
from .registry import AgentToolsetFactory


class RegistryHostWiring(TypedDict):
    extra_toolsets: dict[str, ToolsetDef]
    agent_toolset_factory: AgentToolsetFactory


def build_host_toolsets(
    cwd: Path,
    project_root: Path,
) -> dict[str, ToolsetDef]:
    return build_builtin_toolsets(cwd, project_root)


def build_agent_toolset_factory() -> AgentToolsetFactory:
    def factory(agent_name: str, spec: AgentSpec) -> ToolsetDef:
        return agent_as_toolset(spec, tool_name=agent_name)

    return factory


def build_registry_host_wiring(
    project_root: Path,
    *,
    cwd: Path | None = None,
) -> RegistryHostWiring:
    cwd_path = cwd if cwd is not None else Path.cwd()
    return {
        "extra_toolsets": build_host_toolsets(cwd_path, project_root),
        "agent_toolset_factory": build_agent_toolset_factory(),
    }
