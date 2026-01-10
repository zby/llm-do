"""Invocable registry and builder utilities.

The registry acts as a symbol table for entry names: resolved workers and
tool-backed invocables are bound to names so the runtime can look them up.
"""
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
from pydantic_ai.toolsets import AbstractToolset

from ..toolsets.builtins import build_builtin_toolsets
from ..toolsets.loader import ToolsetBuildContext, build_toolsets
from .args import WorkerArgs
from .contracts import Invocable, ModelType
from .discovery import load_toolsets_and_workers_from_files
from .schema_refs import resolve_schema_ref
from .worker import ToolInvocable, Worker
from .worker_file import load_worker_file


@dataclass(frozen=True, slots=True)
class InvocableRegistry:
    """Symbol table mapping entry names to resolved invocables."""

    entries: dict[str, Invocable]

    def get(self, name: str) -> Invocable:
        """Return the invocable for a name or raise with a helpful error."""
        try:
            return self.entries[name]
        except KeyError as exc:
            available = sorted(self.entries.keys())
            raise ValueError(f"Entry '{name}' not found. Available: {available}") from exc

    def names(self) -> list[str]:
        """Return sorted entry names."""
        return sorted(self.entries.keys())


# Registry of server-side tool factories
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
    *sources: Mapping[str, AbstractToolset[Any]],
) -> dict[str, AbstractToolset[Any]]:
    merged: dict[str, AbstractToolset[Any]] = {}
    for source in sources:
        for name, toolset in source.items():
            if name in merged and merged[name] is not toolset:
                raise ValueError(f"Duplicate toolset name: {name}")
            merged[name] = toolset
    return merged


async def _get_tool_names(toolset: AbstractToolset[Any]) -> list[str]:
    """Get tool names from a toolset without needing a RunContext."""
    from pydantic_ai.toolsets import FunctionToolset
    if isinstance(toolset, FunctionToolset):
        return list(toolset.tools.keys())
    # For other toolsets, we'd need a RunContext - return empty for now
    # Worker returns itself as a single tool
    if isinstance(toolset, Worker):
        return [toolset.name]
    return []


async def build_invocable_registry(
    worker_files: list[str],
    python_files: list[str],
    *,
    entry_name: str = "main",
    entry_model_override: ModelType | None = None,
    set_overrides: list[str] | None = None,
) -> InvocableRegistry:
    """Build the invocable symbol table with toolsets resolved and entries ready."""
    # Load Python toolsets and workers in a single pass
    python_toolsets, python_workers = load_toolsets_and_workers_from_files(python_files)

    # Build map of tool_name -> toolset for code entry pattern
    # Note: duplicate tool names are detected by pydantic-ai at runtime
    python_tool_map: dict[str, tuple[AbstractToolset[Any], str]] = {}
    for toolset_name, toolset in python_toolsets.items():
        tool_names = await _get_tool_names(toolset)
        for tool_name in tool_names:
            if tool_name not in python_tool_map:
                python_tool_map[tool_name] = (toolset, tool_name)

    if not worker_files and not python_tool_map and not python_workers:
        raise ValueError("At least one .worker or .py file with entries required")

    entries: dict[str, Invocable] = {}

    for name, worker in python_workers.items():
        entries[name] = worker

    for tool_name, (toolset, tool_entry_name) in python_tool_map.items():
        if tool_name in entries:
            continue
        entries[tool_name] = ToolInvocable(toolset=toolset, tool_name=tool_entry_name)

    # First pass: create stub Worker instances (they ARE AbstractToolsets)
    worker_entries: dict[str, Worker] = {}
    worker_paths: dict[str, str] = {}  # name -> path

    for worker_path in worker_files:
        worker_file = load_worker_file(worker_path)
        name = worker_file.name

        # Check for duplicate worker names
        if name in worker_entries:
            raise ValueError(f"Duplicate worker name: {name}")

        # Check for conflict with Python entries
        if name in entries:
            raise ValueError(f"Worker name '{name}' conflicts with Python entry")

        stub = Worker(
            name=name,
            instructions=worker_file.instructions,
            description=worker_file.description,
            model=worker_file.model,
            toolsets=[],
        )
        worker_entries[name] = stub
        worker_paths[name] = worker_path

    # Second pass: build all workers with resolved toolsets
    workers: dict[str, Worker] = {}

    for name, worker_path in worker_paths.items():
        # Apply overrides only to entry worker
        overrides = set_overrides if name == entry_name else None
        worker_file = load_worker_file(worker_path, overrides=overrides)

        # Available toolsets: built-ins + Python + workers (including self if referenced)
        # Worker IS an AbstractToolset, so we can use it directly
        available_workers = dict(worker_entries)
        worker_root = Path(worker_path).resolve().parent
        builtin_toolsets = build_builtin_toolsets(Path.cwd(), worker_root)
        all_toolsets = _merge_toolsets(builtin_toolsets, python_toolsets, available_workers)

        # Resolve toolsets: worker refs + python toolsets + (built-in aliases or class paths)
        toolset_context = ToolsetBuildContext(
            worker_name=name,
            worker_path=Path(worker_path).resolve(),
            available_toolsets=all_toolsets,
        )
        resolved_toolsets = build_toolsets(worker_file.toolsets, toolset_context)
        # Apply model override only to entry worker (if override provided)
        worker_model: ModelType | None
        if entry_model_override and name == entry_name:
            worker_model = entry_model_override
        else:
            worker_model = worker_file.model

        # Build builtin tools from server_side_tools config
        builtin_tools = _build_builtin_tools(worker_file.server_side_tools)

        stub = worker_entries[name]
        stub.instructions = worker_file.instructions
        stub.description = worker_file.description
        stub.model = worker_model
        stub.compatible_models = worker_file.compatible_models
        if worker_file.schema_in_ref:
            resolved_schema = resolve_schema_ref(
                worker_file.schema_in_ref,
                base_path=Path(worker_path).resolve().parent,
            )
            if not issubclass(resolved_schema, WorkerArgs):
                raise TypeError(
                    "schema_in_ref must resolve to a WorkerArgs subclass"
                )
            stub.schema_in = cast(type[WorkerArgs], resolved_schema)
        stub.toolsets = resolved_toolsets
        stub.builtin_tools = builtin_tools

        workers[name] = stub

    entries.update(workers)

    return InvocableRegistry(entries=entries)
