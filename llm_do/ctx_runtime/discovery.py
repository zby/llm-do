"""Module loading and AbstractToolset discovery.

This module provides functions to:
- Load Python modules from file paths
- Discover AbstractToolset instances (including FunctionToolset)
- Discover Worker instances

Discovery uses isinstance() checks to find toolset instances
in module attributes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

from pydantic_ai.toolsets import AbstractToolset

from .invocables import Worker


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


def discover_workers_from_module(module: ModuleType) -> list[Worker]:
    """Discover Worker instances from a module.

    Args:
        module: Loaded Python module

    Returns:
        List of discovered workers
    """
    workers: list[Worker] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, Worker):
            workers.append(obj)
    return workers


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


def load_workers_from_files(files: list[str | Path]) -> dict[str, Worker]:
    """Load all Worker instances from multiple Python files.

    Args:
        files: List of paths to Python files

    Returns:
        Dict mapping worker names to instances
    """
    all_workers: dict[str, Worker] = {}
    worker_paths: dict[str, Path] = {}

    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue

        module = load_module(path)
        workers = discover_workers_from_module(module)

        for worker in workers:
            if worker.name in all_workers:
                existing_path = worker_paths[worker.name]
                raise ValueError(
                    f"Duplicate worker name: {worker.name} "
                    f"(from {existing_path} and {path})"
                )
            all_workers[worker.name] = worker
            worker_paths[worker.name] = path

    return all_workers


def load_toolsets_and_workers_from_files(
    files: Iterable[str | Path],
) -> tuple[dict[str, AbstractToolset[Any]], dict[str, Worker]]:
    """Load toolsets and workers from Python files with a single module pass."""
    toolsets: dict[str, AbstractToolset[Any]] = {}
    workers: dict[str, Worker] = {}
    worker_paths: dict[str, Path] = {}
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
        module_workers = discover_workers_from_module(module)

        for name, toolset in module_toolsets.items():
            if name in toolsets:
                raise ValueError(f"Duplicate toolset name: {name}")
            toolsets[name] = toolset

        for worker in module_workers:
            if worker.name in workers:
                existing_path = worker_paths[worker.name]
                raise ValueError(
                    f"Duplicate worker name: {worker.name} "
                    f"(from {existing_path} and {resolved})"
                )
            workers[worker.name] = worker
            worker_paths[worker.name] = resolved

    return toolsets, workers
