"""Module loading and ToolsetSpec discovery."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

from pydantic_ai.toolsets import AbstractToolset

from ..toolsets.loader import ToolsetSpec

_LOADED_MODULES: dict[Path, ModuleType] = {}


def load_module(path: str | Path) -> ModuleType:
    """Load a Python module from a file path."""
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


def discover_toolsets_from_module(module: ModuleType) -> dict[str, ToolsetSpec]:
    """Discover ToolsetSpec instances from a module."""
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


def load_toolsets_from_files(files: list[str | Path]) -> dict[str, ToolsetSpec]:
    """Load ToolsetSpec instances from Python files."""
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


def load_all_from_files(
    files: Iterable[str | Path],
) -> tuple[dict[str, ToolsetSpec], dict[str, Any], dict[str, Any]]:
    """Load toolset specs from Python files.

    This function is kept for backward compatibility but now only loads toolsets.
    Worker and entry discovery is handled by the agent_loader module.

    Args:
        files: Paths to Python files

    Returns:
        Tuple of (toolset specs, empty dict, empty dict)
    """
    toolsets: dict[str, ToolsetSpec] = {}
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

        for name, toolset in module_toolsets.items():
            if name in toolsets:
                raise ValueError(f"Duplicate toolset name: {name}")
            toolsets[name] = toolset

    # Return empty dicts for workers and entries (no longer supported)
    return toolsets, {}, {}
