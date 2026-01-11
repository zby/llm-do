"""Entry registry and builder utilities.

The registry acts as a symbol table for entry names: resolved workers and
entry functions are bound to names so the runtime can look them up.
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
from .worker import Worker, WorkerToolset
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


@dataclass(slots=True)
class WorkerSpec:
    """Per-worker bookkeeping for two-pass registry building."""

    name: str
    path: Path
    definition: WorkerDefinition
    stub: Worker


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

    if not worker_files and not python_workers and not python_entries:
        raise ValueError("At least one .worker or .py file with entries required")

    entries: dict[str, Entry] = {}

    # Add Python workers as entries
    for name, worker in python_workers.items():
        entries[name] = worker

    # Add @entry decorated functions (conflict with workers checked in discovery)
    for name, entry_func in python_entries.items():
        entries[name] = entry_func

    # First pass: load worker definitions and create minimal stub Worker instances
    worker_specs: dict[str, WorkerSpec] = {}

    for worker_file_path in worker_files:
        resolved_path = Path(worker_file_path).resolve()
        frontmatter, instructions = load_worker_file_parts(resolved_path)
        name_value = frontmatter.get("name")
        if not isinstance(name_value, str) or not name_value:
            raise ValueError("Worker file must have a 'name' field")
        name = name_value

        # Check for duplicate worker names
        if name in worker_specs:
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

        # Create minimal stub (fields filled in second pass)
        stub = Worker(name=name, instructions="", toolsets=[])
        worker_specs[name] = WorkerSpec(
            name=name,
            path=resolved_path,
            definition=worker_def,
            stub=stub,
        )

    # Second pass: resolve toolsets and fill in worker stubs
    # Workers are wrapped in WorkerToolset to expose them as tools
    available_workers = {name: WorkerToolset(spec.stub) for name, spec in worker_specs.items()}

    for spec in worker_specs.values():
        worker_root = spec.path.parent
        builtin_toolsets = build_builtin_toolsets(Path.cwd(), worker_root)
        all_toolsets = _merge_toolsets(builtin_toolsets, python_toolsets, available_workers)

        toolset_context = ToolsetBuildContext(
            worker_name=spec.name,
            worker_path=spec.path,
            available_toolsets=all_toolsets,
        )
        resolved_toolsets = build_toolsets(spec.definition.toolsets, toolset_context)

        # Apply model override only to entry worker
        worker_model: ModelType | None
        if entry_model_override is not None and spec.name == entry_name:
            worker_model = entry_model_override
        else:
            worker_model = spec.definition.model

        # Fill in stub fields
        spec.stub.instructions = spec.definition.instructions
        spec.stub.description = spec.definition.description
        spec.stub.model = worker_model
        spec.stub.compatible_models = spec.definition.compatible_models
        spec.stub.toolsets = resolved_toolsets
        spec.stub.builtin_tools = _build_builtin_tools(spec.definition.server_side_tools)

        if spec.definition.schema_in_ref:
            resolved_schema = resolve_schema_ref(
                spec.definition.schema_in_ref,
                base_path=worker_root,
            )
            if not issubclass(resolved_schema, WorkerArgs):
                raise TypeError(
                    "schema_in_ref must resolve to a WorkerArgs subclass"
                )
            spec.stub.schema_in = cast(type[WorkerArgs], resolved_schema)

        entries[spec.name] = spec.stub

    # Resolve toolset refs for EntryFunction instances (build global map only if needed)
    entry_funcs_with_refs = [ef for ef in python_entries.values() if ef.toolset_refs]
    if entry_funcs_with_refs:
        global_builtins = build_builtin_toolsets(Path.cwd(), Path.cwd())
        all_available_toolsets = _merge_toolsets(
            global_builtins, python_toolsets, available_workers
        )
        for entry_func in entry_funcs_with_refs:
            entry_func.resolve_toolsets(all_available_toolsets)

    return EntryRegistry(entries=entries)
