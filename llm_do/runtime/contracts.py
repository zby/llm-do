"""Type contracts for the runtime layer.

This module centralizes the shared type surface between runtime components
without requiring runtime modules to import each other.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from pydantic_ai.models import Model  # Used in ModelType
from pydantic_ai.toolsets import AbstractToolset  # Used in CallRuntimeProtocol

from ..toolsets.loader import ToolsetSpec
from .events import RuntimeEvent

if TYPE_CHECKING:
    from pydantic_ai.tools import RunContext

    from .args import WorkerArgs
    from .call import CallFrame, CallScope
    from .shared import Runtime, RuntimeConfig

ModelType: TypeAlias = str | Model
EventCallback: TypeAlias = Callable[[RuntimeEvent], None]
MessageLogCallback: TypeAlias = Callable[[str, int, list[Any]], None]


class CallRuntimeProtocol(Protocol):
    """Structural type for the runtime object used as PydanticAI deps.

    Minimal surface: config (runtime-scoped settings) + frame (call-scoped state).
    Access settings via config.*, call state via frame.prompt/messages and frame.config.*.
    """

    @property
    def config(self) -> "RuntimeConfig": ...

    @property
    def runtime(self) -> "Runtime": ...

    @property
    def frame(self) -> "CallFrame": ...

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None: ...

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallRuntimeProtocol": ...

    def _make_run_context(self, tool_name: str) -> "RunContext[CallRuntimeProtocol]": ...

    def _validate_tool_args(
        self,
        toolset: AbstractToolset[Any],
        tool: Any,
        input_data: Any,
        run_ctx: "RunContext[CallRuntimeProtocol]",
    ) -> Any: ...


class Entry(Protocol):
    """Protocol for entries that can be invoked via the runtime dispatcher.

    An entry is a named callable with associated toolset specs. AgentEntry and
    EntryFunction both implement this protocol.

    Additional attributes (model, compatible_models) may be accessed via
    getattr with defaults in the runtime.

    schema_in defines an optional WorkerArgs subclass for structured input.
    If None, entries accept string or list[str | Attachment] directly.

    Note: Entry implementations expose both setup and per-turn execution:
    - Entry.start(runtime) -> CallScope (CallScope.run_turn executes per-turn calls)
    - Entry.run_turn(scope, input_data) - per-turn execution within a scope
    - AgentEntry.call(input_data, run_ctx) - used when an entry is invoked as a tool
    - EntryFunction.call(args, messages, scope) - called with args and messages

    Runtime.run_entry() handles the dispatch based on entry type.
    """

    @property
    def name(self) -> str: ...

    def start(
        self,
        runtime: "Runtime",
        *,
        parent: CallRuntimeProtocol | None = None,
        message_history: list[Any] | None = None,
    ) -> "CallScope": ...

    async def run_turn(
        self,
        scope: CallScope,
        input_data: Any,
    ) -> Any: ...

    @property
    def toolset_specs(self) -> list[ToolsetSpec]: ...

    @property
    def schema_in(self) -> type["WorkerArgs"] | None: ...
