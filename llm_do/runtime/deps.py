"""Runtime deps facade for tool execution."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from ..toolsets.loader import ToolsetBuildContext, instantiate_toolsets
from .agent_runner import run_agent
from .approval import wrap_toolsets_for_approval
from .call import CallFrame
from .contracts import AgentSpec, ModelType
from .shared import Runtime, RuntimeConfig
from .toolsets import cleanup_toolsets


class WorkerRuntime:
    """Dispatches tool calls and agent runs, managing call-scoped state.

    WorkerRuntime is the central orchestrator for executing tools and agents.
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
        self._entry_history_consumed = False

    @property
    def config(self) -> RuntimeConfig:
        return self.runtime.config

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(worker_name, depth, messages)

    def reset_entry_history(self) -> None:
        """Allow a new entry turn to pass message history into call_agent."""
        self._entry_history_consumed = False

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "WorkerRuntime":
        """Spawn a child worker runtime with a forked CallFrame (depth+1)."""
        return WorkerRuntime(
            runtime=self.runtime,
            frame=self.frame.fork(
                active_toolsets,
                model=model,
                invocation_name=invocation_name,
            ),
        )

    def _resolve_agent_spec(self, spec_or_name: AgentSpec | str) -> AgentSpec:
        if isinstance(spec_or_name, AgentSpec):
            return spec_or_name
        if not isinstance(spec_or_name, str):
            raise TypeError("call_agent expects AgentSpec or str")
        registry = self.runtime.agent_registry
        try:
            return registry[spec_or_name]
        except KeyError as exc:
            available = sorted(registry.keys())
            raise ValueError(
                f"Agent '{spec_or_name}' not found. Available: {available}"
            ) from exc

    async def call_agent(self, spec_or_name: AgentSpec | str, input_data: Any) -> Any:
        """Invoke a configured agent by spec or name (depth boundary)."""
        if self.frame.config.depth >= self.config.max_depth:
            raise RuntimeError("max_depth exceeded")

        spec = self._resolve_agent_spec(spec_or_name)

        toolset_context = spec.toolset_context or ToolsetBuildContext(
            worker_name=spec.name
        )
        toolsets = instantiate_toolsets(spec.toolset_specs, toolset_context)
        wrapped_toolsets = wrap_toolsets_for_approval(
            toolsets,
            self.config.approval_callback,
            return_permission_errors=self.config.return_permission_errors,
        )

        child_runtime = self.spawn_child(
            active_toolsets=wrapped_toolsets,
            model=spec.model,
            invocation_name=spec.name,
        )

        use_entry_history = (
            self.frame.config.depth == 0 and not self._entry_history_consumed
        )
        message_history = list(self.frame.messages) if use_entry_history else None

        try:
            output, messages = await run_agent(
                spec,
                child_runtime,
                input_data,
                message_history=message_history,
            )
        finally:
            await cleanup_toolsets(toolsets)

        if use_entry_history:
            self.frame.messages[:] = messages
            self._entry_history_consumed = True

        return output
