"""Type contracts for the runtime layer.

This module centralizes the shared type surface between runtime components
without requiring runtime modules to import each other.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai.models import Model  # Used in ModelType
from pydantic_ai.toolsets import AbstractToolset  # Used in WorkerRuntimeProtocol

from ..toolsets.loader import ToolsetSpec
from .events import RuntimeEvent

if TYPE_CHECKING:
    from .args import WorkerArgs
    from .call import CallFrame, CallScope
    from .shared import Runtime, RuntimeConfig

ModelType: TypeAlias = str | Model
EventCallback: TypeAlias = Callable[[RuntimeEvent], None]
MessageLogCallback: TypeAlias = Callable[[str, int, list[Any]], None]


class AgentRuntimeProtocol(Protocol):
    """Protocol for the AgentRuntime deps object passed to PydanticAI agents.

    AgentRuntime provides:
    - Agent registry for delegation via call_agent()
    - Depth tracking via spawn()
    - Per-call toolset instantiation via toolsets_for()
    - Attachment resolution via load_binary()
    - Backward-compatible frame-based API
    """

    @property
    def config(self) -> "RuntimeConfig": ...

    @property
    def depth(self) -> int: ...

    @property
    def agents(self) -> dict[str, Agent[Any, Any]]: ...

    def spawn(self) -> "AgentRuntimeProtocol": ...

    async def call_agent(
        self,
        name: str,
        prompt: str | Sequence[Any],
        *,
        ctx: RunContext["AgentRuntimeProtocol"],
    ) -> Any: ...

    def resolve_path(self, path: str) -> Path: ...

    def load_binary(self, path: str) -> BinaryContent: ...

    def toolsets_for(
        self,
        agent: Agent[Any, Any],
        *,
        agent_name: str | None = None,
    ) -> Sequence[AbstractToolset[Any]]: ...

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None: ...


class WorkerRuntimeProtocol(Protocol):
    """Structural type for the runtime object used as PydanticAI deps.

    Minimal surface: config (runtime-scoped settings) + frame (call-scoped state).
    Access settings via config.*, call state via frame.prompt/messages and frame.config.*.

    Note: This protocol is maintained for backward compatibility. New code should
    use AgentRuntimeProtocol which provides the cleaner spawn/call_agent pattern.
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


class Entry(Protocol):
    """Protocol for entries that can be invoked via the runtime dispatcher.

    An entry is a named callable with associated toolset specs. Worker and
    EntryFunction both implement this protocol.

    Additional attributes (model, compatible_models) may be accessed via
    getattr with defaults in the runtime.

    schema_in defines the WorkerArgs subclass used to normalize entry input
    (None defaults to WorkerInput).

    Note: Entry implementations expose both setup and per-turn execution:
    - Entry.start(runtime) -> CallScope (CallScope.run_turn executes per-turn calls)
    - Entry.run_turn(runtime, input_data) - per-turn execution within a scope
    - Worker.call(input_data, run_ctx) - used when a Worker is invoked as a tool
    - EntryFunction.call(args, runtime) - called directly with WorkerArgs

    Runtime.run_entry() handles the dispatch based on entry type.
    """

    @property
    def name(self) -> str: ...

    def start(
        self,
        runtime: "Runtime",
        *,
        message_history: list[Any] | None = None,
    ) -> "CallScope": ...

    async def run_turn(
        self,
        runtime: WorkerRuntimeProtocol,
        input_data: Any,
    ) -> Any: ...

    @property
    def toolset_specs(self) -> list[ToolsetSpec]: ...

    @property
    def schema_in(self) -> type["WorkerArgs"] | None: ...
