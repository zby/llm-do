"""CallContext deps facade for tool execution."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from ..toolsets.loader import ToolsetSpec
from .agent_runner import run_agent
from .call import CallFrame, CallScope
from .contracts import AgentSpec, ModelType
from .runtime import Runtime, RuntimeConfig


class CallContext:
    """Dispatches agent runs, managing call-scoped state.

    CallContext is the central orchestrator for executing tools and agents.
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

    @property
    def agent_registry(self) -> dict[str, AgentSpec]:
        return self.runtime.agent_registry

    @property
    def toolset_registry(self) -> dict[str, ToolsetSpec]:
        return self.runtime.toolset_registry

    @property
    def dynamic_agents(self) -> dict[str, AgentSpec]:
        return self.runtime.dynamic_agents

    def log_messages(self, agent_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(agent_name, depth, messages)

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallContext":
        """Spawn a child agent runtime with a forked CallFrame (depth+1)."""
        return CallContext(
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
        spec = self._resolve_agent_spec(spec_or_name)

        if self.frame.config.depth >= self.config.max_depth:
            caller = self.frame.config.invocation_name or "entry"
            raise RuntimeError(
                "max_depth exceeded "
                f"(depth={self.frame.config.depth}, max_depth={self.config.max_depth}, "
                f"caller={caller!r}, attempted={spec.name!r})"
            )

        async with CallScope.for_agent(self, spec) as scope:
            output, _messages = await run_agent(
                spec,
                scope.runtime,
                input_data,
            )
            return output
