"""Type contracts for the runtime layer.

This module centralizes the shared type surface between runtime components
without requiring runtime modules to import each other.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from pydantic_ai.models import Model  # Used in ModelType
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset  # Used in WorkerRuntimeProtocol

from ..ui.events import UIEvent

if TYPE_CHECKING:
    from .approval import ApprovalCallback
    from .call import CallFrame
    from .shared import RuntimeConfig

ModelType: TypeAlias = str | Model
EventCallback: TypeAlias = Callable[[UIEvent], None]
MessageLogCallback: TypeAlias = Callable[[str, int, list[Any]], None]


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

    @prompt.setter
    def prompt(self, value: str) -> None: ...

    @property
    def messages(self) -> list[Any]: ...

    @property
    def on_event(self) -> EventCallback | None: ...

    @property
    def verbosity(self) -> int: ...

    @property
    def return_permission_errors(self) -> bool: ...

    @property
    def approval_callback(self) -> "ApprovalCallback": ...

    @property
    def frame(self) -> "CallFrame": ...

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None: ...

    def spawn_child(
        self,
        toolsets: list[AbstractToolset[Any]] | None = None,
        *,
        model: ModelType | None = None,
    ) -> "WorkerRuntimeProtocol": ...


class Invocable(Protocol):
    """Protocol for entries that can be invoked via the runtime dispatcher.

    Worker and ToolInvocable both implement this protocol.
    Worker has additional attributes (model, toolsets, compatible_models)
    that are accessed via getattr with defaults in the runtime.

    The call() signature separates concerns:
    - config: Global scope (immutable, shared across all workers)
    - state: Per-call scope (mutable, forked per-worker)
    - run_ctx: PydanticAI RunContext with WorkerRuntime as deps (for tools)
    """

    @property
    def name(self) -> str: ...

    async def call(
        self,
        input_data: Any,
        config: "RuntimeConfig",
        state: "CallFrame",
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any: ...
