"""Entry resolution helpers for manifest-driven execution."""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Iterable

from .contracts import AgentEntry, Entry, FunctionEntry
from .discovery import load_module
from .manifest import EntryConfig
from .registry import AgentRegistry


def resolve_entry(
    entry_config: EntryConfig,
    registry: AgentRegistry,
    *,
    python_files: Iterable[str | Path],
    base_path: Path | None = None,
) -> Entry:
    """Resolve the entry from manifest config.

    entry_config must specify exactly one of agent or function.
    """
    if entry_config.agent is not None:
        return _resolve_agent_entry(entry_config.agent, registry)
    if entry_config.function is not None:
        return _resolve_function_entry(
            entry_config.function,
            python_files=python_files,
            base_path=base_path,
        )
    raise ValueError("entry config must define an agent or function")


def _resolve_agent_entry(name: str, registry: AgentRegistry) -> Entry:
    spec = registry.agents.get(name)
    if spec is None:
        available = sorted(registry.agents)
        raise ValueError(
            f"Entry agent '{name}' not found. Available agents: {available}"
        )
    return AgentEntry(spec=spec)


def _split_function_ref(function_ref: str) -> tuple[str, str]:
    if ":" not in function_ref:
        raise ValueError(
            "entry.function must use 'path.py:function' syntax"
        )
    module_ref, function_name = function_ref.rsplit(":", 1)
    module_ref = module_ref.strip()
    function_name = function_name.strip()
    if not module_ref or not function_name:
        raise ValueError("entry.function must use 'path.py:function' syntax")
    return module_ref, function_name


def _normalize_python_paths(
    python_files: Iterable[str | Path],
    base_path: Path | None,
) -> set[Path]:
    resolved: set[Path] = set()
    for path in python_files:
        path_obj = Path(path)
        if not path_obj.is_absolute() and base_path is not None:
            path_obj = (base_path / path_obj)
        resolved_path = path_obj.resolve()
        if resolved_path.suffix != ".py":
            continue
        resolved.add(resolved_path)
    return resolved


def _resolve_function_entry(
    function_ref: str,
    *,
    python_files: Iterable[str | Path],
    base_path: Path | None,
) -> FunctionEntry:
    module_ref, function_name = _split_function_ref(function_ref)
    if not _is_path_ref(module_ref):
        raise ValueError("entry.function must use 'path.py:function' syntax")

    path = Path(module_ref).expanduser()
    if not path.is_absolute():
        if base_path is None:
            raise ValueError(
                "entry.function uses a relative path but no base path was provided"
            )
        path = (base_path / path).resolve()
    else:
        path = path.resolve()

    allowed_paths = _normalize_python_paths(python_files, base_path)
    if path not in allowed_paths:
        raise ValueError(
            f"Entry function file not listed in python_files: {path}"
        )

    module = load_module(path)
    value = getattr(module, function_name, None)
    if value is None:
        raise ValueError(
            f"Entry function '{function_name}' not found in '{path}'"
        )
    if isinstance(value, Entry):
        raise TypeError(
            f"entry.function must reference a function, not an Entry ({function_name})"
        )
    if not callable(value):
        raise TypeError(
            f"entry.function must reference a callable, got {type(value)}"
        )
    if not inspect.iscoroutinefunction(value):
        raise TypeError(
            f"entry.function must reference an async function: {function_name}"
        )

    return FunctionEntry(name=function_name, fn=value)


def _is_path_ref(module_ref: str) -> bool:
    return (
        module_ref.endswith(".py")
        or "/" in module_ref
        or "\\" in module_ref
        or module_ref.startswith((".", "~"))
    )
