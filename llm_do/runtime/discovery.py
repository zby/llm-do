"""Module loading and tool/toolset discovery."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable, TypeVar

from pydantic_ai.tools import Tool
from pydantic_ai.toolsets import AbstractToolset

from ..toolsets.loader import (
    ToolDef,
    ToolsetDef,
    is_tool_def,
    is_toolset_def,
    tool_def_name,
)
from .contracts import AgentSpec

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


def _ensure_name_list(raw: object, *, field_name: str) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a list of strings")
    names: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} entries must be non-empty strings")
        names.append(item)
    return names


def _raise_registry_error(kind: str, message: str) -> None:
    raise ValueError(f"Invalid {kind} registry: {message}")


def _validate_tool_entry(name: str, obj: object, *, source: str) -> str | None:
    if not is_tool_def(obj) or isinstance(obj, AbstractToolset):
        return f"{name} ({type(obj).__name__})"
    if isinstance(obj, Tool):
        if obj.name != name:
            return f"{name} (Tool name {obj.name!r})"
        return None
    obj_name = getattr(obj, "__name__", None)
    if not obj_name:
        return f"{name} (missing __name__)"
    if obj_name != name:
        return f"{name} (callable {obj_name!r})"
    return None


def _parse_tools_registry(raw: object, *, source: str) -> dict[str, ToolDef]:
    tools: dict[str, ToolDef] = {}
    errors: list[str] = []
    if isinstance(raw, dict):
        for name, obj in raw.items():
            if not isinstance(name, str) or not name.strip():
                _raise_registry_error("tools", f"{source} keys must be non-empty strings")
            error = _validate_tool_entry(name, obj, source=source)
            if error:
                errors.append(error)
                continue
            tools[name] = obj  # type: ignore[assignment]
        if errors:
            _raise_registry_error(
                "tools",
                f"{source} contains invalid entries: {', '.join(errors)}",
            )
        return tools
    if isinstance(raw, list):
        duplicates: set[str] = set()
        for obj in raw:
            if not is_tool_def(obj) or isinstance(obj, AbstractToolset):
                errors.append(f"{obj!r} ({type(obj).__name__})")
                continue
            name = tool_def_name(obj)  # type: ignore[arg-type]
            if not name:
                errors.append(f"{obj!r} (no usable name)")
                continue
            if name in tools:
                duplicates.add(name)
            tools[name] = obj  # type: ignore[assignment]
        if errors:
            _raise_registry_error(
                "tools",
                f"{source} list contains invalid entries: {', '.join(errors)}",
            )
        if duplicates:
            _raise_registry_error(
                "tools",
                f"{source} list contains duplicate tool names: {sorted(duplicates)}",
            )
        return tools
    _raise_registry_error("tools", f"{source} must be a dict or list")
    return {}


def discover_tools_from_module(module: ModuleType) -> dict[str, ToolDef]:
    tools_raw = getattr(module, "TOOLS", None)
    if tools_raw is not None:
        return _parse_tools_registry(tools_raw, source="TOOLS")

    all_names = getattr(module, "__all__", None)
    if all_names is None:
        return {}

    names = _ensure_name_list(all_names, field_name="__all__")
    tools: dict[str, ToolDef] = {}
    errors: list[str] = []
    for name in names:
        obj = getattr(module, name, None)
        if obj is None:
            errors.append(f"{name} (not found)")
            continue
        error = _validate_tool_entry(name, obj, source="__all__")
        if error:
            errors.append(error)
            continue
        tools[name] = obj  # type: ignore[assignment]
    if errors:
        _raise_registry_error(
            "tools",
            f"__all__ contains invalid entries: {', '.join(errors)}",
        )
    return tools


def _validate_toolset_entry(name: str, obj: object, *, source: str) -> str | None:
    if not is_toolset_def(obj) or isinstance(obj, Tool):
        return f"{name} ({type(obj).__name__})"
    return None


def _parse_toolsets_registry(raw: object, *, source: str) -> dict[str, ToolsetDef]:
    toolsets: dict[str, ToolsetDef] = {}
    errors: list[str] = []
    if isinstance(raw, dict):
        for name, obj in raw.items():
            if not isinstance(name, str) or not name.strip():
                _raise_registry_error("toolsets", f"{source} keys must be non-empty strings")
            error = _validate_toolset_entry(name, obj, source=source)
            if error:
                errors.append(error)
                continue
            toolsets[name] = obj  # type: ignore[assignment]
        if errors:
            _raise_registry_error(
                "toolsets",
                f"{source} contains invalid entries: {', '.join(errors)}",
            )
        return toolsets
    if isinstance(raw, list):
        duplicates: set[str] = set()
        for obj in raw:
            if isinstance(obj, AbstractToolset):
                name = obj.id
                if not name:
                    errors.append(
                        "AbstractToolset without id (use dict for explicit names)"
                    )
                    continue
            elif callable(obj):
                name = getattr(obj, "__name__", None)
                if not name:
                    errors.append("callable missing __name__ (use dict for explicit names)")
                    continue
            else:
                errors.append(f"{obj!r} ({type(obj).__name__})")
                continue
            if name in toolsets:
                duplicates.add(name)
            toolsets[name] = obj  # type: ignore[assignment]
        if errors:
            _raise_registry_error(
                "toolsets",
                f"{source} list contains invalid entries: {', '.join(errors)}",
            )
        if duplicates:
            _raise_registry_error(
                "toolsets",
                f"{source} list contains duplicate toolset names: {sorted(duplicates)}",
            )
        return toolsets
    _raise_registry_error("toolsets", f"{source} must be a dict or list")
    return {}


def discover_toolsets_from_module(module: ModuleType) -> dict[str, ToolsetDef]:
    toolsets_raw = getattr(module, "TOOLSETS", None)
    if toolsets_raw is not None:
        return _parse_toolsets_registry(toolsets_raw, source="TOOLSETS")

    toolsets: dict[str, ToolsetDef] = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, AbstractToolset):
            toolsets[name] = obj
    return toolsets


def discover_agents_from_module(module: ModuleType) -> list[AgentSpec]:
    return _discover_from_module(module, AgentSpec)


def load_toolsets_from_files(files: list[str | Path]) -> dict[str, ToolsetDef]:
    all_toolsets: dict[str, ToolsetDef] = {}
    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue
        for name, toolset in discover_toolsets_from_module(load_module(path)).items():
            if name in all_toolsets:
                raise ValueError(f"Duplicate toolset name: {name}")
            all_toolsets[name] = toolset
    return all_toolsets


def load_tools_from_files(files: list[str | Path]) -> dict[str, ToolDef]:
    all_tools: dict[str, ToolDef] = {}
    for file_path in files:
        path = Path(file_path)
        if path.suffix != ".py":
            continue
        for name, tool in discover_tools_from_module(load_module(path)).items():
            if name in all_tools:
                raise ValueError(f"Duplicate tool name: {name}")
            all_tools[name] = tool
    return all_tools


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
) -> tuple[dict[str, ToolDef], dict[str, ToolsetDef], dict[str, AgentSpec]]:
    """Load tools, toolsets, and agents from Python files.

    Performs a single pass through the modules to discover all items.

    Args:
        files: Paths to Python files

    Returns:
        Tuple of (tools, toolsets, agents) dictionaries
    """
    tools: dict[str, ToolDef] = {}
    toolsets: dict[str, ToolsetDef] = {}
    agents: dict[str, AgentSpec] = {}
    agent_paths: dict[str, Path] = {}
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
        module_tools = discover_tools_from_module(module)
        module_toolsets = discover_toolsets_from_module(module)
        module_agents = discover_agents_from_module(module)

        for name, tool in module_tools.items():
            if name in tools:
                raise ValueError(f"Duplicate tool name: {name}")
            tools[name] = tool

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

    return tools, toolsets, agents
