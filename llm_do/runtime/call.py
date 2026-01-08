"""Per-call scope for workers (config + mutable state)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic_ai.toolsets import AbstractToolset

from .contracts import ModelType


@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""

    toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0


@dataclass(slots=True)
class CallFrame:
    """Per-worker call state with immutable config and mutable conversation state."""

    config: CallConfig

    # Mutable fields (required for runtime behavior)
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    # Convenience accessors for backward compatibility
    @property
    def toolsets(self) -> tuple[AbstractToolset[Any], ...]:
        return self.config.toolsets

    @property
    def model(self) -> ModelType:
        return self.config.model

    @property
    def depth(self) -> int:
        return self.config.depth

    def fork(
        self,
        toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
    ) -> "CallFrame":
        """Create child frame with incremented depth and fresh messages."""
        new_config = CallConfig(
            toolsets=tuple(toolsets) if toolsets is not None else self.config.toolsets,
            model=model if model is not None else self.config.model,
            depth=self.config.depth + 1,
        )
        return CallFrame(config=new_config)
