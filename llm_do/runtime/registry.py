"""Entry/agent registry and builder utilities."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, cast

from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    WebFetchTool,
    WebSearchTool,
)

from ..models import select_model
from ..toolsets.agent import agent_as_toolset
from ..toolsets.builtins import build_builtin_toolsets
from ..toolsets.loader import ToolsetSpec, resolve_toolset_specs
from .args import WorkerArgs
from .contracts import AgentSpec, EntrySpec, WorkerRuntimeProtocol
from .discovery import load_all_from_files
from .schema_refs import resolve_schema_ref
from .worker_file import (
    WorkerDefinition,
    build_worker_definition,
    load_worker_file_parts,
)


@dataclass(frozen=True, slots=True)
class AgentRegistry:
    """Symbol table mapping agent names to AgentSpec instances."""

    agents: dict[str, AgentSpec]


@dataclass(slots=True)
class WorkerSpec:
    """Per-worker bookkeeping for two-pass registry building."""

    name: str
    path: Path
    definition: WorkerDefinition
    spec: AgentSpec


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


def _merge_toolsets(
    *sources: Mapping[str, ToolsetSpec],
) -> dict[str, ToolsetSpec]:
    merged: dict[str, ToolsetSpec] = {}
    for source in sources:
        for name, toolset in source.items():
            if name in merged:
                raise ValueError(f"Duplicate toolset name: {name}")
            merged[name] = toolset
    return merged


def _build_registry_and_entry_spec(
    worker_files: list[str],
    python_files: list[str],
    *,
    project_root: Path | str,
) -> tuple[EntrySpec, AgentRegistry]:
    if project_root is None:
        raise ValueError("project_root is required to build entries")
    project_root_path = Path(project_root).resolve()

    python_toolsets, python_agents, python_entries = load_all_from_files(python_files)

    if not worker_files and not python_agents and not python_entries:
        raise ValueError("At least one .worker or .py file with entries required")

    entry_specs = sorted(python_entries.values(), key=lambda e: e.name)
    if len(entry_specs) > 1:
        entry_names = [entry.name for entry in entry_specs]
        raise ValueError(
            "Multiple EntrySpec instances found: "
            f"{entry_names}. Only one entry is allowed."
        )
    entry_from_python = entry_specs[0] if entry_specs else None

    worker_specs: dict[str, WorkerSpec] = {}
    entry_worker_names: list[str] = []
    reserved_names = set(python_agents.keys()) | set(python_entries.keys())

    for worker_file_path in worker_files:
        resolved_path = Path(worker_file_path).resolve()
        frontmatter, instructions = load_worker_file_parts(resolved_path)
        worker_def = build_worker_definition(frontmatter, instructions)
        name = worker_def.name

        if name in worker_specs:
            raise ValueError(f"Duplicate worker name: {name}")

        if name in reserved_names:
            if name in python_agents:
                raise ValueError(
                    f"Worker name '{name}' conflicts with Python agent"
                )
            raise ValueError(f"Worker name '{name}' conflicts with Python entry")
        reserved_names.add(name)

        if worker_def.entry:
            entry_worker_names.append(name)

        resolved_model = select_model(
            worker_model=worker_def.model,
            compatible_models=worker_def.compatible_models,
            worker_name=name,
        )
        spec = AgentSpec(
            name=name,
            instructions=worker_def.instructions,
            description=worker_def.description,
            model=resolved_model,
            toolset_specs=[],
            builtin_tools=_build_builtin_tools(worker_def.server_side_tools),
        )
        worker_specs[name] = WorkerSpec(
            name=name,
            path=resolved_path,
            definition=worker_def,
            spec=spec,
        )

    if entry_from_python and entry_worker_names:
        raise ValueError(
            "Entry conflict: found Python EntrySpec and entry worker(s) "
            f"{sorted(entry_worker_names)}."
        )
    if len(entry_worker_names) > 1:
        raise ValueError(
            "Multiple workers marked entry: "
            f"{sorted(entry_worker_names)}. Only one entry worker is allowed."
        )

    agents: dict[str, AgentSpec] = dict(python_agents)
    agents.update({spec.name: spec.spec for spec in worker_specs.values()})

    builtin_toolsets = build_builtin_toolsets(Path.cwd(), project_root_path)
    agent_toolsets = {
        name: agent_as_toolset(spec, tool_name=name) for name, spec in agents.items()
    }
    all_toolsets = _merge_toolsets(builtin_toolsets, python_toolsets, agent_toolsets)

    for worker_spec in worker_specs.values():
        worker_root = worker_spec.path.parent
        resolved_toolset_specs = resolve_toolset_specs(
            worker_spec.definition.toolsets,
            available_toolsets=all_toolsets,
            worker_name=worker_spec.name,
        )

        worker_spec.spec.toolset_specs = resolved_toolset_specs

        if worker_spec.definition.schema_in_ref:
            resolved_schema = resolve_schema_ref(
                worker_spec.definition.schema_in_ref,
                base_path=worker_root,
            )
            if not issubclass(resolved_schema, WorkerArgs):
                raise TypeError(
                    "schema_in_ref must resolve to a WorkerArgs subclass"
                )
            worker_spec.spec.schema_in = cast(type[WorkerArgs], resolved_schema)

    if entry_from_python is None and not entry_worker_names:
        raise ValueError(
            "No entry found. Mark one worker with entry: true or "
            "define a single EntrySpec in Python."
        )

    if entry_from_python is not None:
        entry_spec = entry_from_python
    else:
        entry_agent = agents[entry_worker_names[0]]

        async def entry_main(
            input_data: Any,
            runtime: WorkerRuntimeProtocol,
        ) -> Any:
            return await runtime.call_agent(entry_agent, input_data)

        entry_spec = EntrySpec(
            main=entry_main,
            name=entry_agent.name,
            schema_in=entry_agent.schema_in,
        )

    return entry_spec, AgentRegistry(agents=agents)


def build_entry_registry(
    worker_files: list[str],
    python_files: list[str],
    *,
    project_root: Path | str,
) -> AgentRegistry:
    entry_spec, registry = _build_registry_and_entry_spec(
        worker_files,
        python_files,
        project_root=project_root,
    )
    _ = entry_spec
    return registry


def build_entry(
    worker_files: list[str],
    python_files: list[str],
    *,
    project_root: Path | str,
) -> tuple[EntrySpec, AgentRegistry]:
    """Build and return the resolved entry spec with agent registry."""
    return _build_registry_and_entry_spec(
        worker_files,
        python_files,
        project_root=project_root,
    )
