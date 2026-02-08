"""Entry resolution helpers for manifest-driven execution."""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Iterable

from ..runtime.contracts import AgentEntry, Entry, FunctionEntry
from .discovery import load_module
from .manifest import EntryConfig
from .path_refs import is_path_ref, resolve_path_ref, split_ref
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
    return split_ref(
        function_ref,
        delimiter=":",
        error_message="entry.function must use 'path.py:function' syntax",
    )


def _normalize_python_paths(
    python_files: Iterable[str | Path],
    base_path: Path | None,
) -> set[Path]:
    resolved: set[Path] = set()
    for path in python_files:
        resolved_path = resolve_path_ref(
            str(path),
            base_path=base_path,
            allow_cwd_fallback=True,
        )
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
    if not is_path_ref(module_ref):
        raise ValueError("entry.function must use 'path.py:function' syntax")
    path = resolve_path_ref(
        module_ref,
        base_path=base_path,
        error_message="entry.function uses a relative path but no base path was provided",
    )

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
