"""Per-call scope for entries (config + mutable state)."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic_ai.toolsets import CombinedToolset

from .contracts import CallRuntimeProtocol, ModelType
from .events import ToolCallEvent, ToolResultEvent
from .toolsets import cleanup_toolsets

if TYPE_CHECKING:
    from pydantic_ai.toolsets import AbstractToolset

    from .contracts import Entry


@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""

    active_toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0
    invocation_name: str = ""

    @classmethod
    def build(
        cls,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        depth: int,
        invocation_name: str,
    ) -> "CallConfig":
        """Normalize toolsets and construct a CallConfig."""
        return cls(
            active_toolsets=tuple(active_toolsets),
            model=model,
            depth=depth,
            invocation_name=invocation_name,
        )

    def fork(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallConfig":
        """Create a child config with incremented depth."""
        return self.build(
            active_toolsets,
            model=model,
            depth=self.depth + 1,
            invocation_name=invocation_name,
        )


@dataclass(slots=True)
class CallFrame:
    """Per-entry call state with immutable config and mutable conversation state."""

    config: CallConfig

    # Mutable fields (required for runtime behavior)
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    def fork(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallFrame":
        """Create child frame with incremented depth and fresh messages."""
        new_config = self.config.fork(
            active_toolsets,
            model=model,
            invocation_name=invocation_name,
        )
        return CallFrame(config=new_config)


@dataclass(slots=True)
class CallScope:
    """Lifecycle wrapper for an entry call scope (runtime + toolsets)."""

    entry: "Entry"
    runtime: CallRuntimeProtocol
    toolsets: Sequence["AbstractToolset[Any]"]
    _closed: bool = False

    async def run_turn(self, input_data: Any) -> Any:
        if self._closed:
            raise RuntimeError("CallScope is closed")
        return await self.entry.run_turn(self, input_data)

    async def call_tool(self, name: str, input_data: Any) -> Any:
        """Call a tool by name using this scope's active toolsets."""
        if self._closed:
            raise RuntimeError("CallScope is closed")

        run_ctx = self.runtime._make_run_context(name)
        combined_toolset = CombinedToolset(self.runtime.frame.config.active_toolsets)
        tools = await combined_toolset.get_tools(run_ctx)
        tool = tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found. Available: {list(tools.keys())}")

        validated_args = self.runtime._validate_tool_args(
            tool.toolset,
            tool,
            input_data,
            run_ctx,
        )

        call_id = str(uuid.uuid4())[:8]
        worker_name = self.runtime.frame.config.invocation_name or "unknown"

        if self.runtime.config.on_event is not None:
            self.runtime.config.on_event(
                ToolCallEvent(
                    worker=worker_name,
                    tool_name=name,
                    tool_call_id=call_id,
                    args=validated_args,
                    depth=self.runtime.frame.config.depth,
                )
            )

        result = await combined_toolset.call_tool(name, validated_args, run_ctx, tool)

        if self.runtime.config.on_event is not None:
            self.runtime.config.on_event(
                ToolResultEvent(
                    worker=worker_name,
                    depth=self.runtime.frame.config.depth,
                    tool_name=name,
                    tool_call_id=call_id,
                    content=result,
                )
            )

        return result

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await cleanup_toolsets(self.toolsets)

    async def __aenter__(self) -> "CallScope":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
