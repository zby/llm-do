"""Agent registry and builder utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, TypeAlias, cast

from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    WebFetchTool,
    WebSearchTool,
)

from ..models import select_model_with_id
from ..runtime.args import AgentArgs
from ..runtime.contracts import AgentSpec
from ..runtime.tooling import ToolDef, ToolsetDef
from .agent_file import AgentDefinition, build_agent_definition, load_agent_file_parts
from .discovery import load_all_from_files
from .input_model_refs import resolve_input_model_ref
from .tool_resolution import resolve_tool_defs, resolve_toolset_defs


@dataclass(frozen=True, slots=True)
class AgentRegistry:
    """Symbol table mapping agent names to AgentSpec instances."""

    agents: dict[str, AgentSpec]
    tools: dict[str, ToolDef] = field(default_factory=dict)
    toolsets: dict[str, ToolsetDef] = field(default_factory=dict)


@dataclass(slots=True)
class AgentFileSpec:
    """Per-agent bookkeeping for two-pass registry building."""

    name: str
    path: Path
    definition: AgentDefinition
    spec: AgentSpec


AgentToolsetFactory: TypeAlias = Callable[[str, AgentSpec], ToolsetDef]


_BUILTIN_TOOL_FACTORIES: dict[str, Callable[[dict[str, Any]], Any]] = {
    "web_search": lambda cfg: WebSearchTool(
        max_uses=cfg.get("max_uses"),
        blocked_domains=cfg.get("blocked_domains"),
        allowed_domains=cfg.get("allowed_domains"),
    ),
    "web_fetch": lambda cfg: WebFetchTool(),
    "code_execution": lambda cfg: CodeExecutionTool(),
    "image_generation": lambda cfg: ImageGenerationTool(),
}


def _build_builtin_tools(configs: list[dict[str, Any]]) -> list[Any]:
    """Convert server-side tool configs to PydanticAI builtin tool instances."""
    tools: list[Any] = []
    for config in configs:
        tool_type = config.get("tool_type")
        if not tool_type:
            raise ValueError("server_side_tools entry must have 'tool_type'")
        factory = _BUILTIN_TOOL_FACTORIES.get(tool_type)
        if not factory:
            raise ValueError(
                f"Unknown tool_type: {tool_type}. "
                f"Supported: {', '.join(_BUILTIN_TOOL_FACTORIES.keys())}"
            )
        tools.append(factory(config))
    return tools


def _merge_registry(
    kind: str,
    *sources: Mapping[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in sources:
        for name, toolset in source.items():
            if name in merged:
                raise ValueError(f"Duplicate {kind} name: {name}")
            merged[name] = toolset
    return merged


def build_registry(
    agent_files: list[str],
    python_files: list[str],
    *,
    project_root: Path | str,
    extra_toolsets: Mapping[str, ToolsetDef] | None = None,
    agent_toolset_factory: AgentToolsetFactory | None = None,
) -> AgentRegistry:
    if project_root is None:
        raise ValueError("project_root is required to build registry")
    project_root_path = Path(project_root).resolve()
    if not project_root_path.exists():
        raise FileNotFoundError(f"project_root not found: {project_root_path}")

    python_tools, python_toolsets, python_agents = load_all_from_files(python_files)

    if not agent_files and not python_files:
        raise ValueError("At least one agent_files or python_files entry is required")

    agent_file_specs: dict[str, AgentFileSpec] = {}
    reserved_names = set(python_agents.keys())

    for agent_file_path in agent_files:
        resolved_path = Path(agent_file_path).resolve()
        frontmatter, instructions = load_agent_file_parts(resolved_path)
        agent_def = build_agent_definition(frontmatter, instructions)
        name = agent_def.name

        if name in agent_file_specs:
            raise ValueError(f"Duplicate agent name: {name}")

        if name in reserved_names:
            raise ValueError(
                f"Agent name '{name}' conflicts with Python agent"
            )
        reserved_names.add(name)

        selection = select_model_with_id(
            agent_model=agent_def.model,
            compatible_models=agent_def.compatible_models,
            agent_name=name,
        )
        spec = AgentSpec(
            name=name,
            instructions=agent_def.instructions,
            description=agent_def.description,
            model=selection.model,
            model_id=selection.model_id,
            tools=[],
            toolsets=[],
            builtin_tools=_build_builtin_tools(agent_def.server_side_tools),
        )
        agent_file_specs[name] = AgentFileSpec(
            name=name,
            path=resolved_path,
            definition=agent_def,
            spec=spec,
        )

    agents: dict[str, AgentSpec] = dict(python_agents)
    agents.update({spec.name: spec.spec for spec in agent_file_specs.values()})

    if extra_toolsets is None:
        from .host_toolsets import build_host_toolsets

        host_toolsets = build_host_toolsets(Path.cwd(), project_root_path)
    else:
        host_toolsets = dict(extra_toolsets)

    if agent_toolset_factory is None:
        from .host_toolsets import build_agent_toolset_factory

        agent_toolset_factory = build_agent_toolset_factory()

    agent_toolsets = {
        name: agent_toolset_factory(name, spec)
        for name, spec in agents.items()
    }
    all_toolsets = _merge_registry(
        "toolset",
        host_toolsets,
        python_toolsets,
        agent_toolsets,
    )
    all_tools = _merge_registry("tool", python_tools)

    for agent_file_spec in agent_file_specs.values():
        agent_root = agent_file_spec.path.parent
        resolved_tools = resolve_tool_defs(
            agent_file_spec.definition.tools,
            available_tools=all_tools,
            agent_name=agent_file_spec.name,
        )
        resolved_toolsets = resolve_toolset_defs(
            agent_file_spec.definition.toolsets,
            available_toolsets=all_toolsets,
            agent_name=agent_file_spec.name,
        )

        agent_file_spec.spec.tools = resolved_tools
        agent_file_spec.spec.toolsets = resolved_toolsets

        if agent_file_spec.definition.input_model_ref:
            resolved_input_model = resolve_input_model_ref(
                agent_file_spec.definition.input_model_ref,
                base_path=agent_root,
            )
            if not issubclass(resolved_input_model, AgentArgs):
                raise TypeError(
                    "input_model_ref must resolve to an AgentArgs subclass"
                )
            agent_file_spec.spec.input_model = cast(
                type[AgentArgs], resolved_input_model
            )

    return AgentRegistry(agents=agents, tools=all_tools, toolsets=all_toolsets)
