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
from .contracts import Entry, ModelType
from .discovery import load_all_from_files
from .schema_refs import resolve_schema_ref
from .worker import ToolInvocable, Worker, WorkerToolset
from .worker_file import (
    WorkerDefinition,
    build_worker_definition,
    load_worker_file_parts,
)


@dataclass(frozen=True, slots=True)
class EntryRegistry:
    """Symbol table mapping entry names to resolved entries."""

    entries: dict[str, Entry]

    def get(self, name: str) -> Entry:
        """Return the entry for a name or raise with a helpful error."""
        try:
            return self.entries[name]
        except KeyError as exc:
            available = sorted(self.entries.keys())
            raise ValueError(f"Entry '{name}' not found. Available: {available}") from exc

    def names(self) -> list[str]:
        """Return sorted entry names."""
        return sorted(self.entries.keys())


# Backwards compatibility alias
InvocableRegistry = EntryRegistry


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


def _get_tool_names(toolset: AbstractToolset[Any]) -> list[str]:
    """Get tool names from a toolset without needing a RunContext."""
    from pydantic_ai.toolsets import FunctionToolset
    if isinstance(toolset, FunctionToolset):
        return list(toolset.tools.keys())
    # For other toolsets, we'd need a RunContext - return empty for now
    # WorkerToolset returns the wrapped worker as a single tool
    if isinstance(toolset, WorkerToolset):
        return [toolset.worker.name]
    return []


def build_entry_registry(
    worker_files: list[str],
    python_files: list[str],
    *,
    entry_name: str = "main",
    entry_model_override: ModelType | None = None,
    set_overrides: list[str] | None = None,
) -> EntryRegistry:
    """Build the entry symbol table with toolsets resolved and entries ready.

    This function performs two-pass registry building:
    1. First pass: Load all Python toolsets, workers, and entry functions;
       load worker file definitions and create stub Workers.
    2. Second pass: Resolve toolset references for workers and entry functions.

    Args:
        worker_files: Paths to .worker files
        python_files: Paths to .py files with toolsets/workers/entries
        entry_name: Name of the primary entry point (default: "main")
        entry_model_override: Optional model to override on the entry worker
        set_overrides: Optional list of KEY=VALUE overrides for the entry worker

    Returns:
        EntryRegistry with all entries resolved and ready to execute
    """
    # Load Python toolsets, workers, and entry functions in a single pass
    python_toolsets, python_workers, python_entries = load_all_from_files(python_files)

    # Build map of tool_name -> toolset for legacy code entry pattern (ToolInvocable)
    # Note: duplicate tool names are detected by pydantic-ai at runtime
    python_tool_map: dict[str, tuple[AbstractToolset[Any], str]] = {}
    for toolset_name, toolset in python_toolsets.items():
        tool_names = _get_tool_names(toolset)
        for tool_name in tool_names:
            if tool_name not in python_tool_map:
                python_tool_map[tool_name] = (toolset, tool_name)

    if not worker_files and not python_tool_map and not python_workers and not python_entries:
        raise ValueError("At least one .worker or .py file with entries required")

    entries: dict[str, Entry] = {}

    # Add Python workers as entries
    for name, worker in python_workers.items():
        entries[name] = worker

    # Add @entry decorated functions
    for name, entry_func in python_entries.items():
        if name in entries:
            raise ValueError(f"Entry name '{name}' conflicts with worker name")
        entries[name] = entry_func

    # Add legacy ToolInvocable entries for tools not already covered
    for tool_name, (toolset, tool_entry_name) in python_tool_map.items():
        if tool_name in entries:
            continue
        entries[tool_name] = ToolInvocable(toolset=toolset, tool_name=tool_entry_name)

    # First pass: load worker definitions and create stub Worker instances
    worker_entries: dict[str, Worker] = {}
    worker_paths: dict[str, Path] = {}
    worker_defs: dict[str, WorkerDefinition] = {}

    for worker_file_path in worker_files:
        resolved_path = Path(worker_file_path).resolve()
        frontmatter, instructions = load_worker_file_parts(resolved_path)
        name_value = frontmatter.get("name")
        if not isinstance(name_value, str) or not name_value:
            raise ValueError("Worker file must have a 'name' field")
        name = name_value

        # Check for duplicate worker names
        if name in worker_entries:
            raise ValueError(f"Duplicate worker name: {name}")

        # Check for conflict with Python entries
        if name in entries:
            raise ValueError(f"Worker name '{name}' conflicts with Python entry")

        overrides = set_overrides if name == entry_name else None
        worker_def = build_worker_definition(frontmatter, instructions, overrides=overrides)
        if overrides and worker_def.name != name:
            raise ValueError(
                f"Cannot override worker name for '{name}' via --set; "
                "update the worker file or pass --entry to select a different worker."
            )

        stub = Worker(
            name=name,
            instructions=worker_def.instructions,
            description=worker_def.description,
            model=worker_def.model,
            toolsets=[],
        )
        worker_entries[name] = stub
        worker_paths[name] = resolved_path
        worker_defs[name] = worker_def

    # Second pass: build all workers with resolved toolsets
    workers: dict[str, Worker] = {}

    # Build available toolsets map for resolution (builtins + python + worker toolsets)
    # Workers are wrapped in WorkerToolset to expose them as tools
    available_workers = {n: WorkerToolset(w) for n, w in worker_entries.items()}
    # Use cwd-based builtins (can be refined per-worker if needed)
    global_builtins = build_builtin_toolsets(Path.cwd(), Path.cwd())
    all_available_toolsets = _merge_toolsets(global_builtins, python_toolsets, available_workers)

    for name, worker_def in worker_defs.items():
        worker_path = worker_paths[name]

        # Available toolsets: built-ins + Python + workers (including self if referenced)
        worker_root = worker_path.parent
        builtin_toolsets = build_builtin_toolsets(Path.cwd(), worker_root)
        all_toolsets = _merge_toolsets(builtin_toolsets, python_toolsets, available_workers)

        # Resolve toolsets: worker refs + python toolsets + (built-in aliases or class paths)
        toolset_context = ToolsetBuildContext(
            worker_name=name,
            worker_path=worker_path,
            available_toolsets=all_toolsets,
        )
        resolved_toolsets = build_toolsets(worker_def.toolsets, toolset_context)
        # Apply model override only to entry worker (if override provided)
        worker_model: ModelType | None
        if entry_model_override and name == entry_name:
            worker_model = entry_model_override
        else:
            worker_model = worker_def.model

        # Build builtin tools from server_side_tools config
        builtin_tools = _build_builtin_tools(worker_def.server_side_tools)

        stub = worker_entries[name]
        stub.instructions = worker_def.instructions
        stub.description = worker_def.description
        stub.model = worker_model
        stub.compatible_models = worker_def.compatible_models
        if worker_def.schema_in_ref:
            resolved_schema = resolve_schema_ref(
                worker_def.schema_in_ref,
                base_path=worker_root,
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

    # Resolve toolset refs for EntryFunction instances
    for entry_func in python_entries.values():
        if entry_func.toolset_refs:
            entry_func.resolve_toolsets(all_available_toolsets)

    return EntryRegistry(entries=entries)


# Backwards compatibility alias
def build_invocable_registry(
    worker_files: list[str],
    python_files: list[str],
    *,
    entry_name: str = "main",
    entry_model_override: ModelType | None = None,
    set_overrides: list[str] | None = None,
) -> EntryRegistry:
    """Backwards compatibility alias for build_entry_registry."""
    return build_entry_registry(
        worker_files,
        python_files,
        entry_name=entry_name,
        entry_model_override=entry_model_override,
        set_overrides=set_overrides,
    )
