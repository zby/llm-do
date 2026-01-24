"""Type contracts for the runtime layer.

This module centralizes the shared type surface between runtime components
without requiring runtime modules to import each other.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from pydantic import BaseModel
from pydantic_ai.models import Model  # Used in ModelType
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import AbstractToolset  # Used in WorkerRuntimeProtocol

from ..toolsets.loader import ToolsetSpec
from .args import WorkerArgs
from .events import RuntimeEvent

if TYPE_CHECKING:
    from .call import CallFrame
    from .shared import RuntimeConfig

ModelType: TypeAlias = str | Model
EventCallback: TypeAlias = Callable[[RuntimeEvent], None]
MessageLogCallback: TypeAlias = Callable[[str, int, list[Any]], None]


class WorkerRuntimeProtocol(Protocol):
    """Structural type for the runtime object used as PydanticAI deps.

    Minimal surface: config (runtime-scoped settings) + frame (call-scoped state).
    Access settings via config.*, call state via frame.prompt/messages and frame.config.*.
    """

    @property
    def config(self) -> "RuntimeConfig": ...

    @property
    def frame(self) -> "CallFrame": ...

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None: ...

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "WorkerRuntimeProtocol": ...

    async def call_agent(self, spec_or_name: "AgentSpec | str", input_data: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class EntrySpec:
    """Specification for a root entry invocation."""

    main: Callable[[Any, "WorkerRuntimeProtocol"], Awaitable[Any]]
    name: str
    schema_in: type["WorkerArgs"] | None = None

    def __post_init__(self) -> None:
        if self.schema_in is not None and not issubclass(self.schema_in, WorkerArgs):
            raise TypeError(f"schema_in must subclass WorkerArgs; got {self.schema_in}")


@dataclass(slots=True)
class AgentSpec:
    """Configuration for constructing a PydanticAI agent per call."""

    name: str
    instructions: str
    model: ModelType
    toolset_specs: list[ToolsetSpec] = field(default_factory=list)
    description: str | None = None
    schema_in: type["WorkerArgs"] | None = None
    schema_out: type[BaseModel] | None = None
    model_settings: ModelSettings | None = None
    builtin_tools: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.schema_in is not None and not issubclass(self.schema_in, WorkerArgs):
            raise TypeError(f"schema_in must subclass WorkerArgs; got {self.schema_in}")
        if self.schema_out is not None and not issubclass(self.schema_out, BaseModel):
            raise TypeError(f"schema_out must subclass BaseModel; got {self.schema_out}")
        for spec in self.toolset_specs:
            if not isinstance(spec, ToolsetSpec):
                raise TypeError("Agent toolset_specs must contain ToolsetSpec instances.")
