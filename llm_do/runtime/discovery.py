"""Module loading and ToolsetSpec discovery."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable, TypeVar

from pydantic_ai.toolsets import AbstractToolset

from ..toolsets.loader import ToolsetSpec
from .contracts import AgentSpec, EntrySpec

_LOADED_MODULES: dict[Path, ModuleType] = {}


def load_module(path: str | Path) -> ModuleType:
    resolved = Path(path).resolve()
    cached = _LOADED_MODULES.get(resolved)
    if cached is not None:
        return cached
    module_name = (
        f"_llm_do_runtime_{resolved.stem}_{hash(str(resolved)) & 0xFFFFFFFF:08x}"
    )
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    _LOADED_MODULES[resolved] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        _LOADED_MODULES.pop(resolved, None)
        sys.modules.pop(spec.name, None)
        raise
    return module


T = TypeVar("T")


def _discover_from_module(module: ModuleType, target_type: type[T]) -> list[T]:
    discovered: list[T] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, target_type):
            discovered.append(obj)
    return discovered


def discover_toolsets_from_module(module: ModuleType) -> dict[str, ToolsetSpec]:
    toolsets: dict[str, ToolsetSpec] = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, ToolsetSpec):
            toolsets[name] = obj
        elif isinstance(obj, AbstractToolset):
            raise ValueError(f"Toolset '{name}' must be defined as ToolsetSpec.")
    return toolsets


def discover_agents_from_module(module: ModuleType) -> list[AgentSpec]:
    return _discover_from_module(module, AgentSpec)


def discover_entries_from_module(module: ModuleType) -> list[EntrySpec]:
    return _discover_from_module(module, EntrySpec)


def load_toolsets_from_files(files: list[str | Path]) -> dict[str, ToolsetSpec]:
    all_toolsets: dict[str, ToolsetSpec] = {}
    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue
        for name, toolset in discover_toolsets_from_module(load_module(path)).items():
            if name in all_toolsets:
                raise ValueError(f"Duplicate toolset name: {name}")
            all_toolsets[name] = toolset
    return all_toolsets


def load_agents_from_files(files: list[str | Path]) -> dict[str, AgentSpec]:
    all_agents: dict[str, AgentSpec] = {}
    agent_paths: dict[str, Path] = {}
    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue
        for agent in discover_agents_from_module(load_module(path)):
            if agent.name in all_agents:
                raise ValueError(
                    f"Duplicate agent name: {agent.name} (from {agent_paths[agent.name]} and {path})"
                )
            all_agents[agent.name] = agent
            agent_paths[agent.name] = path
    return all_agents


def load_all_from_files(
    files: Iterable[str | Path],
) -> tuple[dict[str, ToolsetSpec], dict[str, AgentSpec], dict[str, EntrySpec]]:
    """Load toolset specs, agents, and entry specs from Python files.

    Performs a single pass through the modules to discover all items.

    Args:
        files: Paths to Python files

    Returns:
        Tuple of (toolset specs, agents, entries) dictionaries
    """
    toolsets: dict[str, ToolsetSpec] = {}
    agents: dict[str, AgentSpec] = {}
    entries: dict[str, EntrySpec] = {}
    agent_paths: dict[str, Path] = {}
    entry_paths: dict[str, Path] = {}
    loaded_paths: set[Path] = set()

    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue
        resolved = path.resolve()
        if resolved in loaded_paths:
            continue
        loaded_paths.add(resolved)

        module = load_module(resolved)
        module_toolsets = discover_toolsets_from_module(module)
        module_agents = discover_agents_from_module(module)
        module_entries = discover_entries_from_module(module)

        for name, toolset in module_toolsets.items():
            if name in toolsets:
                raise ValueError(f"Duplicate toolset name: {name}")
            toolsets[name] = toolset

        for agent in module_agents:
            if agent.name in agents:
                existing_path = agent_paths[agent.name]
                raise ValueError(
                    f"Duplicate agent name: {agent.name} "
                    f"(from {existing_path} and {resolved})"
                )
            agents[agent.name] = agent
            agent_paths[agent.name] = resolved

        for entry in module_entries:
            if entry.name in entries:
                existing_path = entry_paths[entry.name]
                raise ValueError(
                    f"Duplicate entry name: {entry.name} "
                    f"(from {existing_path} and {resolved})"
                )
            entries[entry.name] = entry
            entry_paths[entry.name] = resolved

    return toolsets, agents, entries
