"""Type contracts for the runtime layer.

This module centralizes the shared type surface between runtime components
without requiring runtime modules to import each other.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeAlias

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset

from ..ui.events import UIEvent

ModelType: TypeAlias = str
EventCallback: TypeAlias = Callable[[UIEvent], None]


class WorkerRuntimeProtocol(Protocol):
    """Structural type for the runtime object used as PydanticAI deps."""

    @property
    def depth(self) -> int: ...

    @property
    def max_depth(self) -> int: ...

    @property
    def model(self) -> ModelType: ...

    @property
    def prompt(self) -> str: ...

    @property
    def messages(self) -> list[Any]: ...

    @property
    def on_event(self) -> EventCallback | None: ...

    @property
    def verbosity(self) -> int: ...

    def spawn_child(
        self,
        toolsets: list[AbstractToolset[Any]] | None = None,
        *,
        model: ModelType | None = None,
    ) -> "WorkerRuntimeProtocol": ...


class Invocable(Protocol):
    """Protocol for entries that can be invoked via the runtime dispatcher."""

    kind: str
    model: ModelType | None
    toolsets: list[AbstractToolset[Any]]

    @property
    def name(self) -> str: ...

    async def call(
        self,
        input_data: Any,
        ctx: WorkerRuntimeProtocol,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any: ...
