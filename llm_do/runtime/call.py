"""Per-call scope for entries (config + mutable state)."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from ..toolsets.loader import instantiate_toolsets
from .approval import wrap_toolsets_for_approval
from .contracts import AgentSpec, CallContextProtocol, ModelType

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""

    active_toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0
    invocation_name: str = ""

    @classmethod
    def build(
        cls,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        depth: int,
        invocation_name: str,
    ) -> "CallConfig":
        """Normalize toolsets and construct a CallConfig."""
        return cls(
            active_toolsets=tuple(active_toolsets),
            model=model,
            depth=depth,
            invocation_name=invocation_name,
        )

    def fork(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallConfig":
        """Create a child config with incremented depth."""
        return self.build(
            active_toolsets,
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
    toolsets: Sequence["AbstractToolset[Any]"]
    _closed: bool = False

    @classmethod
    def for_agent(cls, parent: CallContextProtocol, spec: AgentSpec) -> "CallScope":
        toolsets = instantiate_toolsets(spec.toolset_specs)
        wrapped_toolsets = wrap_toolsets_for_approval(
            toolsets,
            parent.config.approval_callback,
            return_permission_errors=parent.config.return_permission_errors,
        )
        child_runtime = parent.spawn_child(
            active_toolsets=wrapped_toolsets,
            model=spec.model,
            invocation_name=spec.name,
        )
        return cls(runtime=child_runtime, toolsets=toolsets)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for toolset in self.toolsets:
            cleanup = getattr(toolset, "cleanup", None)
            if cleanup is None:
                continue
            try:
                result = cleanup()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Toolset cleanup failed for %r", toolset)

    async def __aenter__(self) -> "CallScope":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
