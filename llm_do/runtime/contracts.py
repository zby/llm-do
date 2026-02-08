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

from .args import AgentArgs, PromptInput
from .events import RuntimeEvent
from .tooling import ToolDef, ToolsetDef, is_tool_def, is_toolset_def

if TYPE_CHECKING:
    from .call import CallFrame
    from .runtime import RuntimeConfig

ModelType: TypeAlias = Model
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
    def tool_registry(self) -> dict[str, ToolDef]: ...

    @property
    def toolset_registry(self) -> dict[str, ToolsetDef]: ...

    @property
    def dynamic_agents(self) -> dict[str, "AgentSpec"]: ...


class Entry:
    """Root entry invocation interface."""

    name: str
    input_model: type["AgentArgs"]

    async def run(self, input_data: Any, runtime: "CallContextProtocol") -> Any:
        """Execute the entry."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class FunctionEntry(Entry):
    """Entry backed by a plain async function."""

    name: str
    fn: Callable[[Any, "CallContextProtocol"], Awaitable[Any]]
    input_model: type["AgentArgs"] = PromptInput

    def __post_init__(self) -> None:
        if self.input_model is None:
            raise TypeError("input_model cannot be None; use PromptInput")
        if not issubclass(self.input_model, AgentArgs):
            raise TypeError(
                f"input_model must subclass AgentArgs; got {self.input_model}"
            )

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
    model_id: str | None = None
    tools: list[ToolDef] = field(default_factory=list)
    toolsets: list[ToolsetDef] = field(default_factory=list)
    description: str | None = None
    input_model: type["AgentArgs"] = PromptInput
    output_model: type[BaseModel] | None = None
    model_settings: ModelSettings | None = None
    builtin_tools: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.input_model is None:
            raise TypeError("input_model cannot be None; use PromptInput")
        if not issubclass(self.input_model, AgentArgs):
            raise TypeError(
                f"input_model must subclass AgentArgs; got {self.input_model}"
            )
        if self.output_model is not None and not issubclass(
            self.output_model, BaseModel
        ):
            raise TypeError(
                f"output_model must subclass BaseModel; got {self.output_model}"
            )
        if not isinstance(self.model, Model):
            raise TypeError("AgentSpec.model must be a Model instance.")
        for tool in self.tools:
            if not is_tool_def(tool) or isinstance(tool, AbstractToolset):
                raise TypeError("Agent tools must contain Tool or callable definitions.")
        for toolset in self.toolsets:
            if not is_toolset_def(toolset):
                raise TypeError(
                    "Agent toolsets must contain AbstractToolset or ToolsetFunc definitions."
                )


@dataclass(frozen=True, slots=True)
class AgentEntry(Entry):
    """Entry backed by an AgentSpec."""

    spec: AgentSpec
    name: str = field(init=False)
    input_model: type[AgentArgs] = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.spec, AgentSpec):
            raise TypeError("AgentEntry spec must be an AgentSpec instance.")
        object.__setattr__(self, "name", self.spec.name)
        object.__setattr__(self, "input_model", self.spec.input_model)

    async def run(self, input_data: Any, runtime: "CallContextProtocol") -> Any:
        return await runtime.call_agent(self.spec, input_data)
