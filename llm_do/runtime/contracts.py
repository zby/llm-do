"""Type contracts for the runtime layer.

This module centralizes the shared type surface between runtime components
without requiring runtime modules to import each other.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from pydantic_ai.models import Model  # Used in ModelType
from pydantic_ai.toolsets import AbstractToolset  # Used in WorkerRuntimeProtocol

from ..toolsets.loader import ToolsetSpec
from .events import RuntimeEvent

if TYPE_CHECKING:
    from .approval import ApprovalCallback
    from .args import WorkerArgs
    from .call import CallFrame
    from .shared import RuntimeConfig

ModelType: TypeAlias = str | Model
EventCallback: TypeAlias = Callable[[RuntimeEvent], None]
MessageLogCallback: TypeAlias = Callable[[str, int, list[Any]], None]


class WorkerRuntimeProtocol(Protocol):
    """Structural type for the runtime object used as PydanticAI deps."""

    @property
    def config(self) -> "RuntimeConfig": ...

    @property
    def project_root(self) -> "Path | None": ...

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
        active_toolsets: list[AbstractToolset[Any]] | None = None,
        *,
        model: ModelType | None = None,
        invocation_name: str | None = None,
    ) -> "WorkerRuntimeProtocol": ...


class Entry(Protocol):
    """Protocol for entries that can be invoked via the runtime dispatcher.

    An entry is a named callable with associated toolset specs. Worker and
    EntryFunction both implement this protocol.

    Additional attributes (model, compatible_models) may be accessed via
    getattr with defaults in the runtime.

    schema_in defines the WorkerArgs subclass used to normalize entry input
    (None defaults to WorkerInput).

    Note: Worker and EntryFunction have different call signatures:
    - Worker.call(input_data, run_ctx) - called via WorkerRuntime._execute()
    - EntryFunction.call(args, runtime) - called directly with WorkerArgs

    Runtime.run_entry() handles the dispatch based on entry type.
    """

    @property
    def name(self) -> str: ...

    @property
    def toolset_specs(self) -> list[ToolsetSpec]: ...

    @property
    def schema_in(self) -> type["WorkerArgs"] | None: ...
