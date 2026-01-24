"""Runtime deps facade for call execution."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from .call import CallFrame
from .contracts import ModelType
from .shared import Runtime, RuntimeConfig


class CallRuntime:
    """Manages call runtime state for entries and tools.

    CallRuntime is the central orchestrator for executing tools and workers.
    It holds:
    - runtime (Runtime): shared config and runtime-scoped state
    - frame (CallFrame): per-branch state (prompt/messages + immutable config)

    Access runtime settings via config.*, call state via frame.prompt/messages and frame.config.*.
    """

    def __init__(
        self,
        *,
        runtime: Runtime,
        frame: CallFrame,
    ) -> None:
        self.runtime = runtime
        self.frame = frame

    @property
    def config(self) -> RuntimeConfig:
        return self.runtime.config

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(worker_name, depth, messages)

    def create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self.runtime._create_usage()

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallRuntime":
        """Spawn a child worker runtime with a forked CallFrame (depth+1)."""
        return CallRuntime(
            runtime=self.runtime,
            frame=self.frame.fork(
                active_toolsets,
                model=model,
                invocation_name=invocation_name,
            ),
        )
