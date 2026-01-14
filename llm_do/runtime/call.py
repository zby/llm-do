"""Per-call scope for workers (config + mutable state)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic_ai.toolsets import AbstractToolset

from .contracts import ModelType


@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""

    active_toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0
    invocation_name: str = ""


@dataclass(slots=True)
class CallFrame:
    """Per-worker call state with immutable config and mutable conversation state."""

    config: CallConfig

    # Mutable fields (required for runtime behavior)
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    # Convenience accessors
    @property
    def active_toolsets(self) -> tuple[AbstractToolset[Any], ...]:
        """Toolsets available for this call (with approval wrappers applied)."""
        return self.config.active_toolsets

    @property
    def model(self) -> ModelType:
        return self.config.model

    @property
    def depth(self) -> int:
        return self.config.depth

    @property
    def invocation_name(self) -> str:
        return self.config.invocation_name

    def fork(
        self,
        active_toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
        invocation_name: str | None = None,
    ) -> "CallFrame":
        """Create child frame with incremented depth and fresh messages."""
        new_config = CallConfig(
            active_toolsets=tuple(active_toolsets) if active_toolsets is not None else self.config.active_toolsets,
            model=model if model is not None else self.config.model,
            depth=self.config.depth + 1,
            invocation_name=(
                invocation_name
                if invocation_name is not None
                else self.config.invocation_name
            ),
        )
        return CallFrame(config=new_config)
