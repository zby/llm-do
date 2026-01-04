"""Dynamic toolset loading for workers.

Workers can declare toolsets using either:
- Built-in aliases (e.g. `shell`, `filesystem`)
- Fully-qualified class paths (e.g. `llm_do.toolsets.shell.ShellToolset`)

Toolsets are instantiated via constructor signature introspection:
- If the toolset accepts `config`, the raw YAML mapping (minus `_approval_config`)
  is passed as a dict.
- Otherwise, YAML keys are passed as keyword arguments when they match the
  toolset's `__init__` parameters.
Per-worker approval config is extracted alongside toolset resolution and stored
on the worker, not on toolset instances.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pydantic_ai.toolsets import AbstractToolset

BUILTIN_TOOLSET_ALIASES: dict[str, str] = {
    "shell": "llm_do.toolsets.shell.ShellToolset",
    "filesystem": "llm_do.toolsets.filesystem.FileSystemToolset",
}


@dataclass(frozen=True, slots=True)
class ToolsetBuildContext:
    """Dependencies and lookup tables for toolset construction."""

    worker_name: str
    worker_path: Path | None = None
    available_toolsets: Mapping[str, AbstractToolset[Any]] = field(default_factory=dict)
    toolset_aliases: Mapping[str, str] = field(default_factory=lambda: BUILTIN_TOOLSET_ALIASES)
    cwd: Path = field(default_factory=lambda: Path.cwd())
    sandbox: Any | None = None

    @property
    def worker_dir(self) -> Path | None:
        return self.worker_path.parent if self.worker_path else None


def _resolve_toolset_ref(toolset_ref: str, aliases: Mapping[str, str]) -> str:
    return aliases.get(toolset_ref, toolset_ref)


def _import_class(class_path: str) -> type[AbstractToolset[Any]]:
    """Dynamically import a toolset class from its fully-qualified path."""
    if "." not in class_path:
        raise ValueError(
            f"Toolset reference must be a full class path, got: {class_path!r}"
        )

    module_path, _, class_name = class_path.rpartition(".")
    module = importlib.import_module(module_path)
    value = getattr(module, class_name)

    if not isinstance(value, type):
        raise TypeError(f"{class_path!r} did not resolve to a class (got {type(value)})")
    if not issubclass(value, AbstractToolset):
        raise TypeError(f"{class_path!r} is not a subclass of AbstractToolset")

    return value


def _is_required_param(param: inspect.Parameter) -> bool:
    if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
        return False
    return param.default is inspect.Parameter.empty


def create_toolset(
    toolset_ref: str,
    config: Mapping[str, Any] | None,
    context: ToolsetBuildContext,
) -> AbstractToolset[Any]:
    """Instantiate a toolset from an alias or fully-qualified class path."""
    class_path = _resolve_toolset_ref(toolset_ref, context.toolset_aliases)
    toolset_class = _import_class(class_path)

    config_dict: dict[str, Any] = dict(config) if config else {}
    config_dict.pop("_approval_config", None)

    sig = inspect.signature(toolset_class.__init__)
    params = {k: v for k, v in sig.parameters.items() if k != "self"}
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

    kwargs: dict[str, Any] = {}

    if "config" in params:
        kwargs["config"] = config_dict
    else:
        for key, value in config_dict.items():
            if key in params or accepts_kwargs:
                kwargs[key] = value
            else:
                raise TypeError(
                    f"{class_path}.__init__ does not accept config key {key!r}; "
                    "either add a `config` parameter or update the worker config"
                )

    injected_deps: dict[str, Any] = {
        "sandbox": context.sandbox,
        "cwd": context.cwd,
        "worker_name": context.worker_name,
        "worker_path": context.worker_path,
        "worker_dir": context.worker_dir,
    }

    for dep_name, dep_value in injected_deps.items():
        if dep_name in kwargs:
            raise ValueError(
                f"Toolset config for {toolset_ref!r} conflicts with injected dependency {dep_name!r}"
            )

        dep_param = params.get(dep_name)
        should_inject = dep_param is not None or accepts_kwargs
        if not should_inject:
            continue

        if dep_param is not None and dep_value is None and _is_required_param(dep_param):
            raise ValueError(
                f"{class_path} requires dependency {dep_name!r}, but it was not available"
            )

        if dep_value is not None:
            kwargs[dep_name] = dep_value

    return toolset_class(**kwargs)


def extract_toolset_approval_configs(
    toolsets_definition: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, dict[str, Any]] | None]:
    """Extract per-toolset approval configs in definition order."""
    configs: list[dict[str, dict[str, Any]] | None] = []
    for _toolset_ref, toolset_config in toolsets_definition.items():
        approval_config = None
        if toolset_config:
            approval_config = toolset_config.get("_approval_config")
        configs.append(approval_config)
    return configs


def build_toolsets(
    toolsets_definition: Mapping[str, Mapping[str, Any]],
    context: ToolsetBuildContext,
) -> list[AbstractToolset[Any]]:
    """Build all toolsets declared in a worker file.

    For shared toolsets (from `available_toolsets`), only `_approval_config`
    is permitted; other config keys are rejected since they can't configure
    a shared instance.
    """
    toolsets: list[AbstractToolset[Any]] = []
    for toolset_ref, toolset_config in toolsets_definition.items():
        existing = context.available_toolsets.get(toolset_ref)
        if existing is not None:
            # Shared toolset: allow only approval config (handled per worker)
            other_keys = set(toolset_config or {}) - {"_approval_config"}
            if other_keys:
                raise TypeError(
                    f"Shared toolset {toolset_ref!r} cannot be configured via "
                    f"worker YAML: {sorted(other_keys)}"
                )
            toolsets.append(existing)
            continue

        toolsets.append(
            create_toolset(
                toolset_ref=toolset_ref,
                config=toolset_config,
                context=context,
            )
        )
    return toolsets
