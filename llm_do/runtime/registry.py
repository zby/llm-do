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

from ..toolsets.builtins import build_builtin_toolsets
from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec, resolve_toolset_specs
from .args import WorkerArgs
from .contracts import Entry
from .discovery import load_all_from_files
from .entries import AgentEntry
from .schema_refs import resolve_schema_ref
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
class EntrySpec:
    """Per-entry bookkeeping for two-pass registry building."""

    name: str
    path: Path
    definition: WorkerDefinition
    stub: AgentEntry


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
            if name in merged:
                raise ValueError(f"Duplicate toolset name: {name}")
            merged[name] = toolset
    return merged


def _build_registry_and_entry_name(
    worker_files: list[str],
    python_files: list[str],
    *,
    project_root: Path | str,
) -> tuple[EntryRegistry, str]:
    """Build the entry symbol table and return the resolved entry name.

    This function performs two-pass registry building:
    1. First pass: Load all Python toolsets, workers, and entry functions;
       load worker file definitions and create stub Workers.
    2. Second pass: Resolve toolset references for workers and entry functions.

    Args:
        worker_files: Paths to .worker files
        python_files: Paths to .py files with toolsets/workers/entries
        project_root: Shared project root for filesystem toolsets
    Returns:
        Tuple of (EntryRegistry, entry_name) with entries resolved and ready
    """
    if project_root is None:
        raise ValueError("project_root is required to build entries")
    project_root_path = Path(project_root).resolve()
    # Load Python toolsets, agents, and entry functions in a single pass
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

    # First pass: load worker definitions and create minimal stub AgentEntry instances
    worker_specs: dict[str, EntrySpec] = {}
    entry_worker_names: list[str] = []
    reserved_names = set(python_workers.keys()) | set(python_entries.keys())

    for worker_file_path in worker_files:
        resolved_path = Path(worker_file_path).resolve()
        frontmatter, instructions = load_worker_file_parts(resolved_path)
        worker_def = build_worker_definition(frontmatter, instructions)
        name = worker_def.name

        # Check for duplicate worker names
        if name in worker_specs:
            raise ValueError(f"Duplicate worker name: {name}")

        # Check for conflict with Python workers or entries
        if name in reserved_names:
            if name in python_workers:
                raise ValueError(
                    f"Worker name '{name}' conflicts with Python worker"
                )
            raise ValueError(f"Worker name '{name}' conflicts with Python entry")
        reserved_names.add(name)

        if worker_def.entry:
            entry_worker_names.append(name)

        stub = AgentEntry(
            name=name,
            instructions=worker_def.instructions,
            description=worker_def.description,
            model=worker_def.model,
            compatible_models=worker_def.compatible_models,
            toolset_specs=[],
            builtin_tools=_build_builtin_tools(worker_def.server_side_tools),
        )
        worker_specs[name] = EntrySpec(
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

    # Second pass: resolve toolset specs and fill in entry stubs
    # Entries are wrapped in EntryToolset to expose them as tools
    available_workers = {
        name: spec.stub.as_toolset_spec() for name, spec in worker_specs.items()
    }

    builtin_toolsets = build_builtin_toolsets(Path.cwd(), project_root_path)
    all_toolsets = _merge_toolsets(builtin_toolsets, python_toolsets, available_workers)

    for spec in worker_specs.values():
        worker_root = spec.path.parent
        toolset_context = ToolsetBuildContext(
            worker_name=spec.name,
            available_toolsets=all_toolsets,
        )
        resolved_toolset_specs = resolve_toolset_specs(
            spec.definition.toolsets,
            toolset_context,
        )

        # Fill in stub fields
        spec.stub.toolset_specs = resolved_toolset_specs
        spec.stub.toolset_context = toolset_context

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

    for worker in python_workers.values():
        if worker.toolset_context is None:
            worker.toolset_context = ToolsetBuildContext(
                worker_name=worker.name,
                available_toolsets=all_toolsets,
            )

    # Resolve toolset refs for EntryFunction instances (build global map only if needed)
    entry_funcs_with_refs = [ef for ef in python_entries.values() if ef.toolset_refs]
    if entry_funcs_with_refs:
        for entry_func in entry_funcs_with_refs:
            toolset_context = ToolsetBuildContext(
                worker_name=entry_func.name,
                available_toolsets=all_toolsets,
            )
            entry_func.resolve_toolsets(all_toolsets, toolset_context)

    entries: dict[str, Entry] = {}
    entries.update(python_workers)
    entries.update(python_entries)
    entries.update({spec.name: spec.stub for spec in worker_specs.values()})

    return EntryRegistry(entries=entries), entry_name


def build_entry_registry(
    worker_files: list[str],
    python_files: list[str],
    *,
    project_root: Path | str,
) -> EntryRegistry:
    """Build the entry symbol table with toolsets resolved and entries ready.

    project_root anchors filesystem toolsets like filesystem_project.
    """
    registry, _entry_name = _build_registry_and_entry_name(
        worker_files,
        python_files,
        project_root=project_root,
    )
    return registry


def build_entry(
    worker_files: list[str],
    python_files: list[str],
    *,
    project_root: Path | str,
) -> Entry:
    """Build and return the single resolved entry.

    project_root anchors filesystem toolsets like filesystem_project.
    """
    registry, entry_name = _build_registry_and_entry_name(
        worker_files,
        python_files,
        project_root=project_root,
    )
    return registry.get(entry_name)
