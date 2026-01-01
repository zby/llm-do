"""Dynamic toolset loading for workers.

Workers can declare toolsets using either:
- Built-in aliases (e.g. `shell`, `filesystem`)
- Fully-qualified class paths (e.g. `llm_do.toolsets.shell.ShellToolset`)

Toolsets are instantiated via constructor signature introspection:
- If the toolset accepts `config`, the raw YAML mapping (minus `_approval_config`)
  is passed as a dict.
- Otherwise, YAML keys are passed as keyword arguments when they match the
  toolset's `__init__` parameters.

Per-worker approval config is handled via ToolsetRef wrappers that carry
`_approval_config` without mutating shared toolset instances.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from pydantic_ai.toolsets import AbstractToolset


class ToolsetRef(AbstractToolset[Any]):
    """A delegating wrapper that carries per-worker approval config.

    This avoids mutating shared toolset instances when multiple workers
    reference the same Python toolset with different `_approval_config`.
    """

    def __init__(
        self,
        inner: AbstractToolset[Any],
        approval_config: dict[str, dict[str, Any]] | None,
    ):
        self._inner = inner
        self._approval_config = approval_config

    @property
    def id(self) -> Optional[str]:
        return getattr(self._inner, "id", None)

    def __getattr__(self, name: str) -> Any:
        # Delegate attribute access to inner toolset
        return getattr(self._inner, name)

    async def get_tools(self, ctx: Any) -> dict:
        return await self._inner.get_tools(ctx)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: Any,
    ) -> Any:
        return await self._inner.call_tool(name, tool_args, ctx, tool)

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: Any = None,
    ) -> Any:
        inner_fn = getattr(self._inner, "needs_approval", None)
        if callable(inner_fn):
            return inner_fn(name, tool_args, ctx, config)
        # No needs_approval on inner; approval layer will use _approval_config
        return None

    def get_approval_description(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
    ) -> str:
        inner_fn = getattr(self._inner, "get_approval_description", None)
        if callable(inner_fn):
            return inner_fn(name, tool_args, ctx)
        args_str = ", ".join(f"{k}={v!r}" for k, v in tool_args.items())
        return f"{name}({args_str})"

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
    approval_config = config_dict.pop("_approval_config", None)

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

    toolset = toolset_class(**kwargs)
    if approval_config is not None:
        setattr(toolset, "_approval_config", approval_config)
    return toolset


def build_toolsets(
    toolsets_definition: Mapping[str, Mapping[str, Any]],
    context: ToolsetBuildContext,
) -> list[AbstractToolset[Any]]:
    """Build all toolsets declared in a worker file.

    For shared toolsets (from `available_toolsets`), per-worker `_approval_config`
    is wrapped via ToolsetRef to avoid mutating shared instances. Other config
    keys are rejected for shared refs since they can't configure a shared instance.
    """
    toolsets: list[AbstractToolset[Any]] = []
    for toolset_ref, toolset_config in toolsets_definition.items():
        existing = context.available_toolsets.get(toolset_ref)
        if existing is not None:
            # Shared toolset: wrap with ToolsetRef if approval config is present
            approval_cfg = toolset_config.get("_approval_config") if toolset_config else None
            other_keys = set(toolset_config or {}) - {"_approval_config"}
            if other_keys:
                raise TypeError(
                    f"Shared toolset {toolset_ref!r} cannot be configured via "
                    f"worker YAML: {sorted(other_keys)}"
                )
            if approval_cfg:
                toolsets.append(ToolsetRef(existing, approval_cfg))
            else:
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

