"""Per-call scope for entries (config + mutable state)."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai._run_context import RunContext
from pydantic_ai.toolsets import AbstractToolset, ToolsetFunc
from pydantic_ai.toolsets._dynamic import DynamicToolset
from pydantic_ai.usage import RunUsage
from pydantic_ai_blocking_approval import ApprovalToolset

from ..toolsets.loader import ToolDef, ToolsetDef, tool_def_name
from .approval import ApprovalDeniedResultToolset, wrap_toolsets_for_approval
from .contracts import AgentSpec, CallContextProtocol, ModelType

logger = logging.getLogger(__name__)


def _toolset_registry_name(toolset: AbstractToolset[Any]) -> str:
    name = getattr(toolset, "_llm_do_registry_name", None)
    if name:
        return name
    return toolset.label


def _unwrap_approval_toolset(toolset: AbstractToolset[Any]) -> AbstractToolset[Any]:
    current = toolset
    while isinstance(current, (ApprovalDeniedResultToolset, ApprovalToolset)):
        current = getattr(current, "_inner", current)
    return current


def _copy_registry_name(source: Any, dest: Any) -> None:
    name = getattr(source, "_llm_do_registry_name", None)
    if name:
        try:
            setattr(dest, "_llm_do_registry_name", name)
        except Exception:
            return


def _toolset_func_label(toolset_func: Any) -> str:
    return (
        getattr(toolset_func, "_llm_do_registry_name", None)
        or getattr(toolset_func, "__name__", None)
        or repr(toolset_func)
    )


def _wrap_toolset_func_for_approval(
    toolset_func: ToolsetFunc[Any],
    *,
    approval_callback: Any,
    return_permission_errors: bool,
) -> Any:
    label = _toolset_func_label(toolset_func)

    async def _wrapped(ctx: Any) -> AbstractToolset[Any] | None:
        toolset = toolset_func(ctx)
        if inspect.isawaitable(toolset):
            toolset = await toolset
        if toolset is None:
            return None
        if not isinstance(toolset, AbstractToolset):
            raise TypeError(
                f"Toolset '{label}' factory returned {type(toolset)!r}; "
                "expected AbstractToolset or None."
            )
        wrapped = wrap_toolsets_for_approval(
            [toolset],
            approval_callback,
            return_permission_errors=return_permission_errors,
        )[0]
        return wrapped

    _copy_registry_name(toolset_func, _wrapped)
    return _wrapped


def _prepare_toolsets_for_run(
    toolsets: Sequence[ToolsetDef],
    *,
    approval_callback: Any,
    return_permission_errors: bool,
) -> list[AbstractToolset[Any]]:
    prepared: list[AbstractToolset[Any]] = []
    for toolset in toolsets:
        if isinstance(toolset, DynamicToolset):
            wrapped_func = _wrap_toolset_func_for_approval(
                toolset.toolset_func,
                approval_callback=approval_callback,
                return_permission_errors=return_permission_errors,
            )
            dynamic = DynamicToolset(
                toolset_func=wrapped_func,
                per_run_step=toolset.per_run_step,
            )
            _copy_registry_name(toolset, dynamic)
            prepared.append(dynamic)
            continue

        if isinstance(toolset, AbstractToolset):
            wrapped = wrap_toolsets_for_approval(
                [toolset],
                approval_callback,
                return_permission_errors=return_permission_errors,
            )[0]
            _copy_registry_name(toolset, wrapped)
            prepared.append(wrapped)
            continue

        wrapped_func = _wrap_toolset_func_for_approval(
            toolset,
            approval_callback=approval_callback,
            return_permission_errors=return_permission_errors,
        )
        dynamic = DynamicToolset(toolset_func=wrapped_func, per_run_step=False)
        _copy_registry_name(toolset, dynamic)
        prepared.append(dynamic)

    return prepared


def _add_source(sources: dict[str, list[str]], name: str, source: str) -> None:
    sources.setdefault(name, []).append(source)


@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""

    active_toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0
    invocation_name: str = ""

    def fork(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallConfig":
        """Create a child config with incremented depth."""
        return CallConfig(
            active_toolsets=tuple(active_toolsets),
            model=model,
            depth=self.depth + 1,
            invocation_name=invocation_name,
        )


@dataclass(slots=True)
class CallFrame:
    """Per-agent call state with immutable config and mutable conversation state."""

    config: CallConfig

    # Mutable fields (required for runtime behavior)
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    def fork(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallFrame":
        """Create child frame with incremented depth and fresh messages."""
        new_config = self.config.fork(
            active_toolsets,
            model=model,
            invocation_name=invocation_name,
        )
        return CallFrame(config=new_config)


@dataclass(slots=True)
class CallScope:
    """Lifecycle wrapper for a call scope (runtime + toolsets)."""

    runtime: CallContextProtocol
    toolsets: Sequence[AbstractToolset[Any]]
    tools: Sequence[ToolDef]
    _closed: bool = False

    @classmethod
    def for_agent(cls, parent: CallContextProtocol, spec: AgentSpec) -> "CallScope":
        toolsets = _prepare_toolsets_for_run(
            spec.toolsets,
            approval_callback=parent.config.approval_callback,
            return_permission_errors=parent.config.return_permission_errors,
        )
        child_runtime = parent.spawn_child(
            active_toolsets=toolsets,
            model=spec.model,
            invocation_name=spec.name,
        )
        return cls(runtime=child_runtime, toolsets=toolsets, tools=spec.tools)

    async def _preflight_tool_name_conflicts(self) -> None:
        sources: dict[str, list[str]] = {}
        for tool in self.tools:
            name = tool_def_name(tool)
            _add_source(sources, name, f"tool:{name}")

        run_ctx = RunContext(
            deps=self.runtime,
            model=self.runtime.frame.config.model,
            usage=RunUsage(),
        )

        for toolset in self.toolsets:
            base_toolset = _unwrap_approval_toolset(toolset)
            if isinstance(base_toolset, DynamicToolset):
                continue
            source_label = _toolset_registry_name(base_toolset)
            try:
                tool_defs = await toolset.get_tools(run_ctx)
            except Exception:
                logger.debug("Toolset preflight failed for %s", source_label, exc_info=True)
                continue
            for name in tool_defs:
                _add_source(sources, name, f"toolset:{source_label}")

        duplicates = {
            name: srcs for name, srcs in sources.items() if len(srcs) > 1
        }
        if not duplicates:
            return

        details = "; ".join(
            f"{name} from {', '.join(sorted(srcs))}"
            for name, srcs in sorted(duplicates.items())
        )
        raise ValueError(
            "Duplicate tool names detected: "
            f"{details}. Rename tools or wrap toolsets with PrefixedToolset."
        )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

    async def __aenter__(self) -> "CallScope":
        await self._preflight_tool_name_conflicts()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
