"""Module loading and AbstractToolset discovery.

This module provides functions to:
- Load Python modules from file paths
- Discover AbstractToolset instances (including FunctionToolset)
- Discover WorkerEntry instances

Discovery uses isinstance() checks to find toolset instances
in module attributes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from .entries import WorkerEntry


def load_module(path: str | Path) -> ModuleType:
    """Load a Python module from a file path.

    Args:
        path: Path to Python file

    Returns:
        Loaded module

    Raises:
        ImportError: If module cannot be loaded
    """
    path = Path(path).resolve()
    # Use full path as module name to avoid collisions between files with same stem
    # e.g., /foo/tools.py and /bar/tools.py become unique module names
    module_name = f"_llm_do_runtime_{path.stem}_{hash(str(path)) & 0xFFFFFFFF:08x}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def discover_toolsets_from_module(module: ModuleType) -> dict[str, AbstractToolset[Any]]:
    """Discover AbstractToolset instances from a module.

    Scans module attributes for instances of AbstractToolset
    (including FunctionToolset) and returns them by attribute name.

    Args:
        module: Loaded Python module

    Returns:
        Dict mapping attribute names to toolset instances
    """
    toolsets: dict[str, AbstractToolset[Any]] = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, AbstractToolset):
            toolsets[name] = obj
    return toolsets


def discover_entries_from_module(module: ModuleType) -> list[WorkerEntry]:
    """Discover WorkerEntry instances from a module.

    Args:
        module: Loaded Python module

    Returns:
        List of discovered entries
    """
    entries: list[WorkerEntry] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, WorkerEntry):
            entries.append(obj)
    return entries


def load_toolsets_from_files(files: list[str | Path]) -> dict[str, AbstractToolset[Any]]:
    """Load all toolsets from multiple Python files.

    Args:
        files: List of paths to Python files

    Returns:
        Dict mapping toolset names to instances

    Raises:
        ValueError: If duplicate toolset names are found
    """
    all_toolsets: dict[str, AbstractToolset[Any]] = {}

    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue

        module = load_module(path)
        toolsets = discover_toolsets_from_module(module)

        for name, toolset in toolsets.items():
            if name in all_toolsets:
                raise ValueError(f"Duplicate toolset name: {name}")
            all_toolsets[name] = toolset

    return all_toolsets


def load_entries_from_files(files: list[str | Path]) -> dict[str, WorkerEntry]:
    """Load all WorkerEntry instances from multiple Python files.

    Args:
        files: List of paths to Python files

    Returns:
        Dict mapping entry names to instances
    """
    all_entries: dict[str, WorkerEntry] = {}

    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue

        module = load_module(path)
        entries = discover_entries_from_module(module)

        for entry in entries:
            all_entries[entry.name] = entry

    return all_entries


