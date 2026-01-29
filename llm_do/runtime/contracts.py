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
from pydantic_ai.toolsets import AbstractToolset  # Used in CallContextProtocol

from ..models import resolve_model
from ..toolsets.loader import ToolsetSpec
from .args import AgentArgs
from .events import RuntimeEvent

if TYPE_CHECKING:
    from .call import CallFrame
    from .runtime import RuntimeConfig

ModelType: TypeAlias = str | Model
EventCallback: TypeAlias = Callable[[RuntimeEvent], None]
MessageLogCallback: TypeAlias = Callable[[str, int, list[Any]], None]


class CallContextProtocol(Protocol):
    """Structural type for the runtime object used as PydanticAI deps.

    Minimal surface: config (runtime-scoped settings) + frame (call-scoped state).
    Access settings via config.*, call state via frame.prompt/messages and frame.config.*.
    """

    @property
    def config(self) -> "RuntimeConfig": ...

    @property
    def frame(self) -> "CallFrame": ...

    def log_messages(self, agent_name: str, depth: int, messages: list[Any]) -> None: ...

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallContextProtocol": ...

    async def call_agent(self, spec_or_name: "AgentSpec | str", input_data: Any) -> Any: ...

    @property
    def agent_registry(self) -> dict[str, "AgentSpec"]: ...

    @property
    def toolset_registry(self) -> dict[str, ToolsetSpec]: ...

    @property
    def dynamic_agents(self) -> dict[str, "AgentSpec"]: ...


class Entry:
    """Root entry invocation interface."""

    name: str
    schema_in: type["AgentArgs"] | None

    async def run(self, input_data: Any, runtime: "CallContextProtocol") -> Any:
        """Execute the entry."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class FunctionEntry(Entry):
    """Entry backed by a plain async function."""

    name: str
    fn: Callable[[Any, "CallContextProtocol"], Awaitable[Any]]
    schema_in: type["AgentArgs"] | None = None

    def __post_init__(self) -> None:
        if self.schema_in is not None and not issubclass(self.schema_in, AgentArgs):
            raise TypeError(f"schema_in must subclass AgentArgs; got {self.schema_in}")

    @classmethod
    def from_function(
        cls,
        fn: Callable[[Any, "CallContextProtocol"], Awaitable[Any]],
    ) -> "FunctionEntry":
        """Create a FunctionEntry using the function name as the entry name."""
        return cls(name=fn.__name__, fn=fn)

    async def run(self, input_data: Any, runtime: "CallContextProtocol") -> Any:
        return await self.fn(input_data, runtime)


@dataclass(slots=True)
class AgentSpec:
    """Configuration for constructing a PydanticAI agent per call."""

    name: str
    instructions: str
    model: ModelType
    toolset_specs: list[ToolsetSpec] = field(default_factory=list)
    description: str | None = None
    schema_in: type["AgentArgs"] | None = None
    schema_out: type[BaseModel] | None = None
    model_settings: ModelSettings | None = None
    builtin_tools: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.schema_in is not None and not issubclass(self.schema_in, AgentArgs):
            raise TypeError(f"schema_in must subclass AgentArgs; got {self.schema_in}")
        if self.schema_out is not None and not issubclass(self.schema_out, BaseModel):
            raise TypeError(f"schema_out must subclass BaseModel; got {self.schema_out}")
        if isinstance(self.model, str):
            self.model = resolve_model(self.model)
        for spec in self.toolset_specs:
            if not isinstance(spec, ToolsetSpec):
                raise TypeError("Agent toolset_specs must contain ToolsetSpec instances.")


@dataclass(frozen=True, slots=True)
class AgentEntry(Entry):
    """Entry backed by an AgentSpec."""

    spec: AgentSpec
    name: str = field(init=False)
    schema_in: type[AgentArgs] | None = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.spec, AgentSpec):
            raise TypeError("AgentEntry spec must be an AgentSpec instance.")
        object.__setattr__(self, "name", self.spec.name)
        object.__setattr__(self, "schema_in", self.spec.schema_in)

    async def run(self, input_data: Any, runtime: "CallContextProtocol") -> Any:
        return await runtime.call_agent(self.spec, input_data)
