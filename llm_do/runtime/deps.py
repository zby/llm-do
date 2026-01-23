"""Runtime deps facade for tool execution.

This module provides AgentRuntime, the deps object passed to PydanticAI agents.
AgentRuntime follows the pattern from experiments/pydanticai-runtime-deps:
- Agent registry for delegation via call_agent()
- Depth tracking via spawn()
- Per-call toolset instantiation via toolsets_for()
- Attachment resolution
- Thread-safe usage collection and message logging
"""
from __future__ import annotations

import mimetypes
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai.models import Model, infer_model
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset
from pydantic_ai.usage import RunUsage

from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec, instantiate_toolsets
from .approval import wrap_toolsets_for_approval
from .call import CallConfig, CallFrame
from .contracts import ModelType
from .events import ToolCallEvent, ToolResultEvent

if TYPE_CHECKING:
    from .shared import Runtime, RuntimeConfig


@dataclass(frozen=True)
class AttachmentResolver:
    """Resolves attachment paths to absolute paths and loads binary content."""

    path_map: Mapping[str, Path] = field(default_factory=dict)
    base_path: Path | None = None

    def resolve_path(self, path: str) -> Path:
        """Resolve a path using the path map or base path."""
        resolved = self.path_map.get(path)
        if resolved is not None:
            return resolved
        file_path = Path(path).expanduser()
        if not file_path.is_absolute() and self.base_path is not None:
            file_path = self.base_path.expanduser() / file_path
        return file_path.resolve()

    def load_binary(self, path: str) -> BinaryContent:
        """Load a file as BinaryContent with inferred media type."""
        resolved = self.resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Attachment not found: {resolved}")

        media_type, _ = mimetypes.guess_type(str(resolved))
        if media_type is None:
            media_type = "application/octet-stream"

        data = resolved.read_bytes()
        return BinaryContent(data=data, media_type=media_type)


@dataclass(frozen=True)
class ToolsetResolver:
    """Resolves and instantiates toolsets for agents."""

    toolset_specs: Mapping[str, Sequence[ToolsetSpec]] = field(default_factory=dict)
    toolset_registry: Mapping[str, ToolsetSpec] = field(default_factory=dict)

    def build_for(
        self,
        agent_name: str | None,
        fallback_toolsets: Sequence[AbstractToolset[Any]] | None = None,
    ) -> list[AbstractToolset[Any]]:
        """Build toolsets for an agent by name, or return fallback."""
        if agent_name:
            specs = self.toolset_specs.get(agent_name)
            if specs:
                context = ToolsetBuildContext(
                    worker_name=agent_name,
                    available_toolsets=dict(self.toolset_registry),
                )
                return instantiate_toolsets(list(specs), context)
        return list(fallback_toolsets or ())


@dataclass
class AgentRuntime:
    """Runtime context passed as deps to PydanticAI agents.

    AgentRuntime is the central orchestrator for executing agents and tools.
    It provides:
    - Agent registry for delegation via call_agent()
    - Depth tracking via spawn() to prevent infinite recursion
    - Per-call toolset instantiation via toolsets_for()
    - Attachment resolution via load_binary()
    - Thread-safe usage collection and message logging via shared Runtime

    This follows the pattern from experiments/pydanticai-runtime-deps while
    maintaining compatibility with the existing llm-do runtime.
    """

    # Shared runtime (config + thread-safe sinks)
    runtime: "Runtime"

    # Agent registry for delegation
    agents: dict[str, Agent[Any, Any]] = field(default_factory=dict)

    # Toolset configuration
    toolset_specs: dict[str, Sequence[ToolsetSpec]] = field(default_factory=dict)
    toolset_registry: dict[str, ToolsetSpec] = field(default_factory=dict)

    # Attachment handling
    attachment_resolver: AttachmentResolver = field(
        default_factory=lambda: AttachmentResolver()
    )

    # Depth tracking
    max_depth: int | None = None  # None means use runtime.config.max_depth
    depth: int = 0

    # Per-call state (backward compatibility with WorkerRuntime)
    frame: CallFrame | None = None

    # Event stream handler for delegation
    event_stream_handler: Any | None = None

    # Internal resolvers (built in __post_init__)
    _toolset_resolver: ToolsetResolver = field(init=False)

    def __post_init__(self) -> None:
        self._toolset_resolver = ToolsetResolver(
            toolset_specs=self.toolset_specs,
            toolset_registry=self.toolset_registry,
        )

    @property
    def config(self) -> "RuntimeConfig":
        """Access shared runtime configuration."""
        return self.runtime.config

    @property
    def effective_max_depth(self) -> int:
        """Get the effective max depth from instance or config."""
        if self.max_depth is not None:
            return self.max_depth
        return self.config.max_depth

    def spawn(self) -> "AgentRuntime":
        """Spawn a child runtime with incremented depth.

        Raises RuntimeError if max depth would be exceeded.
        """
        if self.depth >= self.effective_max_depth:
            raise RuntimeError(
                f"max_depth exceeded: {self.depth} >= {self.effective_max_depth}"
            )
        return replace(self, depth=self.depth + 1, frame=None)

    async def call_agent(
        self,
        name: str,
        prompt: str | Sequence[Any],
        *,
        ctx: RunContext["AgentRuntime"],
    ) -> Any:
        """Call a registered agent by name.

        This is the primary delegation mechanism for agent-to-agent calls.
        The child agent runs with incremented depth and fresh toolsets.
        """
        agent = self.agents.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name}. Available: {list(self.agents.keys())}")

        child = self.spawn()
        toolsets = child.toolsets_for(agent, agent_name=name)

        result = await agent.run(
            prompt,
            deps=child,
            usage=ctx.usage,
            event_stream_handler=self.event_stream_handler,
            toolsets=toolsets,
        )
        return result.output

    def resolve_path(self, path: str) -> Path:
        """Resolve an attachment path to an absolute path."""
        return self.attachment_resolver.resolve_path(path)

    def load_binary(self, path: str) -> BinaryContent:
        """Load an attachment as BinaryContent."""
        return self.attachment_resolver.load_binary(path)

    def toolsets_for(
        self,
        agent: Agent[Any, Any],
        *,
        agent_name: str | None = None,
    ) -> Sequence[AbstractToolset[Any]]:
        """Build and wrap toolsets for an agent call.

        Toolsets are instantiated fresh per-call and wrapped with approval
        policies based on runtime configuration.
        """
        resolved_name = agent_name or self._resolve_agent_name(agent)
        toolsets = self._toolset_resolver.build_for(
            resolved_name,
            fallback_toolsets=agent.toolsets,
        )

        if not toolsets:
            return []

        # Apply approval wrapping
        wrapped = wrap_toolsets_for_approval(
            toolsets,
            self.config.approval_callback,
            return_permission_errors=self.config.return_permission_errors,
        )
        return list(wrapped)

    def _resolve_agent_name(self, agent: Agent[Any, Any]) -> str | None:
        """Find the registered name for an agent."""
        for name, candidate in self.agents.items():
            if candidate is agent:
                return name
        return None

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(worker_name, depth, messages)

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self.runtime._create_usage()

    # =========================================================================
    # Backward compatibility with WorkerRuntime interface
    # =========================================================================

    def _make_run_context(self, tool_name: str) -> RunContext["AgentRuntime"]:
        """Construct a RunContext for direct tool invocation."""
        if self.frame is None:
            raise RuntimeError("Cannot make RunContext without a CallFrame")

        model: Model = (
            infer_model(self.frame.config.model)
            if isinstance(self.frame.config.model, str)
            else self.frame.config.model
        )
        return RunContext(
            deps=self,
            model=model,
            usage=self._create_usage(),
            prompt=self.frame.prompt,
            messages=list(self.frame.messages),
            run_step=self.frame.config.depth,
            retry=0,
            tool_name=tool_name,
        )

    def _validate_tool_args(
        self,
        toolset: AbstractToolset[Any],
        tool: Any,
        input_data: Any,
        run_ctx: RunContext["AgentRuntime"],
    ) -> Any:
        """Validate tool args for direct calls to match PydanticAI behavior."""
        args = input_data
        if isinstance(args, BaseModel):
            args = args.model_dump()
        validator = tool.args_validator
        if isinstance(args, (str, bytes, bytearray)):
            json_input = args if args else "{}"
            validated = validator.validate_json(
                json_input,
                allow_partial="off",
                context=run_ctx.validation_context,
            )
            return validated

        if args is None:
            args = {}
        validated = validator.validate_python(
            args,
            allow_partial="off",
            context=run_ctx.validation_context,
        )
        return validated

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "AgentRuntime":
        """Spawn a child runtime with a forked CallFrame (depth+1).

        This maintains backward compatibility with the WorkerRuntime interface.
        """
        if self.frame is None:
            raise RuntimeError("Cannot spawn_child without a CallFrame")

        new_frame = self.frame.fork(
            active_toolsets,
            model=model,
            invocation_name=invocation_name,
        )
        return replace(self, frame=new_frame, depth=new_frame.config.depth)

    async def call(self, name: str, input_data: Any) -> Any:
        """Call a tool by name (searched across toolsets).

        This enables programmatic tool invocation from code entry points:
            result = await ctx.deps.call("pitch_evaluator", {"input": "..."})
        """
        if self.frame is None:
            raise RuntimeError("Cannot call tools without a CallFrame")

        run_ctx = self._make_run_context(name)

        combined_toolset = CombinedToolset(self.frame.config.active_toolsets)
        tools = await combined_toolset.get_tools(run_ctx)
        tool = tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found. Available: {list(tools.keys())}")

        validated_args = self._validate_tool_args(
            tool.toolset,
            tool,
            input_data,
            run_ctx,
        )

        call_id = str(uuid.uuid4())[:8]
        worker_name = self.frame.config.invocation_name or "unknown"

        if self.config.on_event is not None:
            self.config.on_event(
                ToolCallEvent(
                    worker=worker_name,
                    tool_name=name,
                    tool_call_id=call_id,
                    args=validated_args,
                    depth=self.frame.config.depth,
                )
            )

        result = await combined_toolset.call_tool(name, validated_args, run_ctx, tool)

        if self.config.on_event is not None:
            self.config.on_event(
                ToolResultEvent(
                    worker=worker_name,
                    depth=self.frame.config.depth,
                    tool_name=name,
                    tool_call_id=call_id,
                    content=result,
                )
            )

        return result


# Backward compatibility alias
WorkerRuntime = AgentRuntime
