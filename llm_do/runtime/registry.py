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
from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec, build_toolsets
from .args import WorkerArgs
from .contracts import Entry, ModelType
from .discovery import load_all_from_files
from .schema_refs import resolve_schema_ref
from .shared import TOOLSET_INSTANCE_ATTR
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
    *sources: Mapping[str, ToolsetSpec],
) -> dict[str, ToolsetSpec]:
    merged: dict[str, ToolsetSpec] = {}
    for source in sources:
        for name, toolset in source.items():
            if name in merged and merged[name] is not toolset:
                raise ValueError(f"Duplicate toolset name: {name}")
            merged[name] = toolset
    return merged


def _parse_entry_marker(raw: Any, *, worker_name: str, worker_path: Path) -> bool:
    """Parse and validate the entry marker in worker frontmatter."""
    if raw is None:
        return False
    if not isinstance(raw, bool):
        raise ValueError(
            f"Invalid entry marker for worker '{worker_name}' in {worker_path}: "
            "expected boolean"
        )
    return raw


def _build_registry_and_entry_name(
    worker_files: list[str],
    python_files: list[str],
    *,
    entry_model_override: ModelType | None = None,
    set_overrides: list[str] | None = None,
) -> tuple[EntryRegistry, str]:
    """Build the entry symbol table and return the resolved entry name.

    This function performs two-pass registry building:
    1. First pass: Load all Python toolsets, workers, and entry functions;
       load worker file definitions and create stub Workers.
    2. Second pass: Resolve toolset references for workers and entry functions.

    Args:
        worker_files: Paths to .worker files
        python_files: Paths to .py files with toolsets/workers/entries
        entry_model_override: Optional model to override on the entry worker
        set_overrides: Optional list of KEY=VALUE overrides for the entry worker

    Returns:
        Tuple of (EntryRegistry, entry_name) with entries resolved and ready
    """
    # Load Python toolsets, workers, and entry functions in a single pass
    python_toolsets, python_workers, python_entries = load_all_from_files(python_files)

    if not worker_files and not python_workers and not python_entries:
        raise ValueError("At least one .worker or .py file with entries required")

    entry_func_names = sorted(python_entries.keys())
    if len(entry_func_names) > 1:
        raise ValueError(
            "Multiple @entry functions found: "
            f"{entry_func_names}. Only one entry function is allowed."
        )
    entry_func_name = entry_func_names[0] if entry_func_names else None
    if entry_func_name and set_overrides:
        raise ValueError(
            "--set overrides only apply to worker entries; "
            "remove --set or use a worker entry instead."
        )
    if set_overrides:
        from ..config import parse_set_override

        for set_spec in set_overrides:
            key_path, _ = parse_set_override(set_spec)
            if key_path == "entry" or key_path.startswith("entry."):
                raise ValueError(
                    "Cannot override entry marker via --set; update the worker frontmatter instead."
                )

    entries: dict[str, Entry] = {}

    # Add Python workers as entries
    for name, worker in python_workers.items():
        entries[name] = worker

    # Add @entry decorated functions (conflict with workers checked in discovery)
    for name, entry_func in python_entries.items():
        entries[name] = entry_func

    # First pass: load worker definitions and create minimal stub Worker instances
    worker_specs: dict[str, WorkerSpec] = {}
    entry_worker_names: list[str] = []

    for worker_file_path in worker_files:
        resolved_path = Path(worker_file_path).resolve()
        frontmatter, instructions = load_worker_file_parts(resolved_path)
        name_value = frontmatter.get("name")
        if not isinstance(name_value, str) or not name_value:
            raise ValueError("Worker file must have a 'name' field")
        name = name_value

        entry_marker = _parse_entry_marker(
            frontmatter.get("entry"),
            worker_name=name,
            worker_path=resolved_path,
        )
        if entry_marker:
            entry_worker_names.append(name)

        # Check for duplicate worker names
        if name in worker_specs:
            raise ValueError(f"Duplicate worker name: {name}")

        # Check for conflict with Python entries
        if name in entries:
            raise ValueError(f"Worker name '{name}' conflicts with Python entry")

        overrides = set_overrides if entry_marker else None
        worker_def = build_worker_definition(frontmatter, instructions, overrides=overrides)
        if overrides and worker_def.name != name:
            raise ValueError(
                f"Cannot override worker name for '{name}' via --set; "
                "update the worker file instead."
            )

        # Create minimal stub (fields filled in second pass)
        stub = Worker(name=name, instructions="", toolsets=[])
        worker_specs[name] = WorkerSpec(
            name=name,
            path=resolved_path,
            definition=worker_def,
            stub=stub,
        )

    if entry_func_name and entry_worker_names:
        raise ValueError(
            "Entry conflict: found @entry function "
            f"'{entry_func_name}' and entry worker(s) {sorted(entry_worker_names)}."
        )
    if len(entry_worker_names) > 1:
        raise ValueError(
            "Multiple workers marked entry: "
            f"{sorted(entry_worker_names)}. Only one entry worker is allowed."
        )
    if not entry_func_name and not entry_worker_names:
        raise ValueError(
            "No entry found. Mark one worker with entry: true or define a single @entry function."
        )

    entry_name = entry_func_name or entry_worker_names[0]

    created_toolsets: list[AbstractToolset[Any]] = []
    created_toolset_ids: set[int] = set()

    def _track_toolsets(toolsets: list[AbstractToolset[Any]]) -> None:
        for toolset in toolsets:
            toolset_id = id(toolset)
            if toolset_id in created_toolset_ids:
                continue
            created_toolset_ids.add(toolset_id)
            created_toolsets.append(toolset)

    def _worker_toolset_spec(worker: Worker) -> ToolsetSpec:
        def factory(_ctx: ToolsetBuildContext) -> AbstractToolset[Any]:
            return WorkerToolset(worker)

        return ToolsetSpec(factory=factory)

    # Second pass: resolve toolsets and fill in worker stubs
    # Workers are wrapped in WorkerToolset to expose them as tools
    available_workers = {
        name: _worker_toolset_spec(spec.stub) for name, spec in worker_specs.items()
    }

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
        _track_toolsets(resolved_toolsets)

        # Apply model override only to entry worker
        worker_model: ModelType | None
        if entry_model_override is not None and spec.name in entry_worker_names:
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

    for worker in python_workers.values():
        if worker.toolsets:
            _track_toolsets(list(worker.toolsets))

    # Resolve toolset refs for EntryFunction instances (build global map only if needed)
    entry_funcs_with_refs = [ef for ef in python_entries.values() if ef.toolset_refs]
    if entry_funcs_with_refs:
        global_builtins = build_builtin_toolsets(Path.cwd(), Path.cwd())
        all_available_toolsets = _merge_toolsets(
            global_builtins, python_toolsets, available_workers
        )
        for entry_func in entry_funcs_with_refs:
            toolset_context = ToolsetBuildContext(
                worker_name=entry_func.name,
                available_toolsets=all_available_toolsets,
            )
            entry_func.resolve_toolsets(all_available_toolsets, toolset_context)
            _track_toolsets(list(entry_func.toolsets))

    entry = entries[entry_name]
    setattr(entry, TOOLSET_INSTANCE_ATTR, list(created_toolsets))

    return EntryRegistry(entries=entries), entry_name


def build_entry_registry(
    worker_files: list[str],
    python_files: list[str],
    *,
    entry_model_override: ModelType | None = None,
    set_overrides: list[str] | None = None,
) -> EntryRegistry:
    """Build the entry symbol table with toolsets resolved and entries ready."""
    registry, _entry_name = _build_registry_and_entry_name(
        worker_files,
        python_files,
        entry_model_override=entry_model_override,
        set_overrides=set_overrides,
    )
    return registry


def build_entry(
    worker_files: list[str],
    python_files: list[str],
    *,
    entry_model_override: ModelType | None = None,
    set_overrides: list[str] | None = None,
) -> Entry:
    """Build and return the single resolved entry."""
    registry, entry_name = _build_registry_and_entry_name(
        worker_files,
        python_files,
        entry_model_override=entry_model_override,
        set_overrides=set_overrides,
    )
    return registry.get(entry_name)
