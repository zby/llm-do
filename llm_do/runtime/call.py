"""Per-call scope for entries (config + mutable state)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from .contracts import ModelType, WorkerRuntimeProtocol
from .toolsets import cleanup_toolsets


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
    """Per-worker call state with immutable config and mutable conversation state."""

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

    runtime: WorkerRuntimeProtocol
    toolsets: Sequence["AbstractToolset[Any]"]
    _closed: bool = False

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await cleanup_toolsets(self.toolsets)

    async def __aenter__(self) -> "CallScope":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
