"""Dynamic toolset loader for class-path based configuration."""
from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Mapping

from pydantic_ai.toolsets import AbstractToolset


BUILTIN_TOOLSET_ALIASES: dict[str, str] = {
    "shell": "llm_do.toolsets.shell.ShellToolset",
    "filesystem": "llm_do.toolsets.filesystem.FileSystemToolset",
}


@dataclass
class ToolsetBuildContext:
    """Context for toolset creation and dependency injection."""

    available_toolsets: Mapping[str, AbstractToolset[Any]] | None = None
    approval_callback: Any | None = None
    deps: Mapping[str, Any] | None = None
    aliases: Mapping[str, str] = field(default_factory=lambda: BUILTIN_TOOLSET_ALIASES)

    def get_dep(self, name: str) -> Any:
        if not self.deps:
            return None
        return self.deps.get(name)


def _import_class(class_path: str) -> type[Any]:
    """Dynamically import a class from its fully-qualified path."""

    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def create_toolset(
    class_path: str,
    config: Mapping[str, Any] | None,
    context: ToolsetBuildContext,
    approval_callback: Any | None = None,
) -> AbstractToolset[Any]:
    """Instantiate a toolset, injecting known dependencies if requested."""

    toolset_class = _import_class(class_path)
    config = dict(config or {})
    approval_config = config.pop("_approval_config", {})

    sig = inspect.signature(toolset_class.__init__)
    accepts_kwargs = any(
        param.kind is inspect.Parameter.VAR_KEYWORD
        for param in sig.parameters.values()
    )

    kwargs: dict[str, Any] = {}
    if "config" in sig.parameters or accepts_kwargs:
        kwargs["config"] = config
    elif config:
        raise TypeError(
            f"Toolset {class_path} does not accept a 'config' parameter"
        )

    available_deps = context.deps or {}
    for dep_name, dep_value in available_deps.items():
        if dep_name in sig.parameters or accepts_kwargs:
            kwargs[dep_name] = dep_value

    toolset = toolset_class(**kwargs)

    if approval_config:
        toolset._approval_config = approval_config  # type: ignore[attr-defined]

    return toolset


def build_toolsets(
    definition: Mapping[str, Mapping[str, Any] | None],
    context: ToolsetBuildContext,
) -> list[AbstractToolset[Any]]:
    """Build toolsets from a mapping of class paths to config."""

    toolsets: list[AbstractToolset[Any]] = []
    available = context.available_toolsets or {}

    for toolset_key, toolset_config in definition.items():
        config = dict(toolset_config or {})
        approval_config = config.pop("_approval_config", {})

        if toolset_key in available:
            toolset = available[toolset_key]
        else:
            class_path = context.aliases.get(toolset_key, toolset_key)
            toolset = create_toolset(
                class_path=class_path,
                config=config,
                context=context,
                approval_callback=context.approval_callback,
            )

        if approval_config:
            toolset._approval_config = approval_config  # type: ignore[attr-defined]

        toolsets.append(toolset)

    return toolsets
