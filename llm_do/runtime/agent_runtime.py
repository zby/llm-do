"""AgentRuntime: PydanticAI deps object for agent delegation and policy."""

from __future__ import annotations

import mimetypes
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping, Sequence

from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai.usage import RunUsage

from ..toolsets.loader import (
    ToolsetBuildContext,
    ToolsetSpec,
    instantiate_toolsets,
)
from .events import RuntimeEvent, ToolCallEvent, ToolResultEvent

if TYPE_CHECKING:
    from pydantic_ai.toolsets import AbstractToolset
    from pydantic_ai_blocking_approval import ApprovalCallback, ApprovalConfig

    from .approval import ApprovalPolicy

EventCallback = Callable[[RuntimeEvent], None]
MessageLogCallback = Callable[[str, int, list[Any]], None]


@dataclass(frozen=True)
class AttachmentResolver:
    """Resolves attachment paths and loads binary content."""

    path_map: Mapping[str, Path] = field(default_factory=dict)
    base_path: Path | None = None

    def resolve_path(self, path: str) -> Path:
        """Resolve a path string to an absolute Path."""
        resolved = self.path_map.get(path)
        if resolved is not None:
            return resolved
        file_path = Path(path).expanduser()
        if not file_path.is_absolute() and self.base_path is not None:
            file_path = self.base_path.expanduser() / file_path
        return file_path.resolve()

    def load_binary(self, path: str) -> BinaryContent:
        """Load binary content from a path with inferred media type."""
        resolved_path = self.resolve_path(path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Attachment not found: {resolved_path}")
        media_type, _ = mimetypes.guess_type(str(resolved_path))
        if media_type is None:
            media_type = "application/octet-stream"
        data = resolved_path.read_bytes()
        return BinaryContent(data=data, media_type=media_type)


@dataclass(frozen=True)
class ToolsetResolver:
    """Resolves and instantiates toolsets for agents."""

    toolset_specs: Mapping[str, Sequence[ToolsetSpec]] = field(default_factory=dict)
    toolset_registry: Mapping[str, ToolsetSpec] = field(default_factory=dict)

    def build_for(
        self,
        agent_name: str | None,
        fallback_toolsets: Sequence[Any] | None = None,
    ) -> list[Any]:
        """Build toolsets for a given agent name."""
        if agent_name:
            specs = self.toolset_specs.get(agent_name) or []
            if specs:
                context = ToolsetBuildContext(
                    worker_name=agent_name,
                    available_toolsets=self.toolset_registry,
                )
                return instantiate_toolsets(list(specs), context)
        return list(fallback_toolsets or ())


@dataclass(frozen=True)
class ApprovalWrapper:
    """Wraps toolsets with approval policy."""

    approval_callback: "ApprovalCallback | None" = None
    approval_config: "ApprovalConfig | None" = None
    capability_map: Mapping[str, Sequence[str]] | None = None
    capability_rules: Mapping[str, str] | None = None
    capability_default: str = "needs_approval"
    approval_policy: "ApprovalPolicy | None" = None
    return_permission_errors: bool = False

    def wrap(self, toolsets: Sequence[Any]) -> list[Any]:
        """Wrap toolsets with approval handling."""
        if not toolsets:
            return []
        if self.approval_callback is None:
            return list(toolsets)

        from .approval_wrapper import wrap_toolsets_with_capabilities

        return wrap_toolsets_with_capabilities(
            toolsets=list(toolsets),
            approval_callback=self.approval_callback,
            approval_config=self.approval_config,
            capability_rules=self.capability_rules,
            capability_map=self.capability_map,
            capability_default=self.capability_default,
            approval_policy=self.approval_policy,
            return_permission_errors=self.return_permission_errors,
        )


class UsageCollector:
    """Thread-safe sink for RunUsage objects."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usages: list[RunUsage] = []

    def create(self) -> RunUsage:
        """Create and track a new RunUsage."""
        usage = RunUsage()
        with self._lock:
            self._usages.append(usage)
        return usage

    def all(self) -> list[RunUsage]:
        """Return all collected usages."""
        with self._lock:
            return list(self._usages)


class MessageAccumulator:
    """Thread-safe sink for message logging across agents."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: list[tuple[str, int, Any]] = []

    def append(self, agent_name: str, depth: int, message: Any) -> None:
        """Append a single message."""
        with self._lock:
            self._messages.append((agent_name, depth, message))

    def extend(self, agent_name: str, depth: int, messages: list[Any]) -> None:
        """Extend with multiple messages."""
        with self._lock:
            self._messages.extend((agent_name, depth, msg) for msg in messages)

    def all(self) -> list[tuple[str, int, Any]]:
        """Return all collected messages."""
        with self._lock:
            return list(self._messages)

    def for_agent(self, agent_name: str) -> list[Any]:
        """Return messages for a specific agent."""
        with self._lock:
            return [msg for name, _, msg in self._messages if name == agent_name]


@dataclass
class AgentRuntime:
    """Runtime deps object for PydanticAI agents.

    AgentRuntime is passed as `deps` to PydanticAI agents. It provides:
    - Agent registry for delegation
    - Depth tracking for recursion limits
    - Toolset resolution and approval wrapping
    - Attachment loading
    - Usage and message accumulation
    """

    # Agent registry
    agents: dict[str, Agent[Any, Any]] = field(default_factory=dict)

    # Attachment resolution
    attachment_resolver: AttachmentResolver = field(
        default_factory=AttachmentResolver
    )

    # Toolset resolution
    toolset_specs: dict[str, Sequence[ToolsetSpec]] = field(default_factory=dict)
    toolset_registry: dict[str, ToolsetSpec] = field(default_factory=dict)

    # Approval configuration
    approval_callback: "ApprovalCallback | None" = None
    approval_config: "ApprovalConfig | None" = None
    capability_map: dict[str, Sequence[str]] | None = None
    capability_rules: dict[str, str] | None = field(
        default_factory=lambda: {"proc.exec.unlisted": "blocked"}
    )
    capability_default: str = "needs_approval"
    approval_policy: "ApprovalPolicy | None" = None
    return_permission_errors: bool = False

    # Depth tracking
    max_depth: int = 5
    depth: int = 0

    # Event handling
    on_event: EventCallback | None = None
    message_log_callback: MessageLogCallback | None = None
    event_stream_handler: Any | None = None
    verbosity: int = 0

    # Project context
    project_root: Path | None = None

    # Shared sinks (set in __post_init__)
    _usage_collector: UsageCollector = field(init=False)
    _message_accumulator: MessageAccumulator = field(init=False)
    _toolset_resolver: ToolsetResolver = field(init=False)
    _approval_wrapper: ApprovalWrapper = field(init=False)

    def __post_init__(self) -> None:
        # Initialize shared sinks only at depth 0
        if self.depth == 0:
            object.__setattr__(self, "_usage_collector", UsageCollector())
            object.__setattr__(self, "_message_accumulator", MessageAccumulator())
        # Build helper objects
        object.__setattr__(
            self,
            "_toolset_resolver",
            ToolsetResolver(
                toolset_specs=self.toolset_specs,
                toolset_registry=self.toolset_registry,
            ),
        )
        object.__setattr__(
            self,
            "_approval_wrapper",
            ApprovalWrapper(
                approval_callback=self.approval_callback,
                approval_config=self.approval_config,
                capability_map=self.capability_map,
                capability_rules=self.capability_rules,
                capability_default=self.capability_default,
                approval_policy=self.approval_policy,
                return_permission_errors=self.return_permission_errors,
            ),
        )

    def spawn(self) -> "AgentRuntime":
        """Create a child runtime with incremented depth.

        Child runtimes share usage and message sinks with the parent.
        """
        if self.depth >= self.max_depth:
            raise RuntimeError(
                f"max_depth exceeded: {self.depth} >= {self.max_depth}"
            )
        child = replace(self, depth=self.depth + 1)
        # Share sinks from parent
        object.__setattr__(child, "_usage_collector", self._usage_collector)
        object.__setattr__(child, "_message_accumulator", self._message_accumulator)
        return child

    async def call_agent(
        self,
        name: str,
        prompt: str | Sequence[Any],
        *,
        ctx: RunContext["AgentRuntime"],
    ) -> Any:
        """Call a registered agent by name.

        This is the primary delegation mechanism used by tools.
        """
        agent = self.agents.get(name)
        if agent is None:
            available = sorted(self.agents.keys())
            raise KeyError(f"Unknown agent: {name}. Available: {available}")

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

    # Attachment helpers
    def resolve_path(self, path: str) -> Path:
        """Resolve an attachment path."""
        return self.attachment_resolver.resolve_path(path)

    def load_binary(self, path: str) -> BinaryContent:
        """Load binary content from a path."""
        return self.attachment_resolver.load_binary(path)

    # Toolset helpers
    def _resolve_agent_name(self, agent: Agent[Any, Any]) -> str | None:
        """Look up an agent's name in the registry."""
        for name, candidate in self.agents.items():
            if candidate is agent:
                return name
        return None

    def _build_toolsets(
        self,
        agent: Agent[Any, Any],
        *,
        agent_name: str | None,
    ) -> list[Any]:
        """Build toolsets for an agent."""
        return self._toolset_resolver.build_for(
            agent_name,
            agent.toolsets,
        )

    def toolsets_for(
        self,
        agent: Agent[Any, Any],
        *,
        agent_name: str | None = None,
    ) -> Sequence[Any]:
        """Get wrapped toolsets for an agent."""
        resolved_name = agent_name or self._resolve_agent_name(agent)
        toolsets = self._build_toolsets(agent, agent_name=resolved_name)
        return self._approval_wrapper.wrap(toolsets)

    # Usage and message tracking
    def create_usage(self) -> RunUsage:
        """Create a new tracked RunUsage."""
        return self._usage_collector.create()

    @property
    def usage(self) -> list[RunUsage]:
        """All collected usage data."""
        return self._usage_collector.all()

    def log_messages(
        self, agent_name: str, depth: int, messages: list[Any]
    ) -> None:
        """Log messages to the accumulator."""
        self._message_accumulator.extend(agent_name, depth, messages)
        if self.message_log_callback is not None:
            self.message_log_callback(agent_name, depth, messages)

    @property
    def message_log(self) -> list[tuple[str, int, Any]]:
        """All logged messages."""
        return self._message_accumulator.all()

    # Event emission
    def emit_tool_call(
        self,
        agent_name: str,
        tool_name: str,
        tool_call_id: str,
        args: dict[str, Any],
    ) -> None:
        """Emit a tool call event."""
        if self.on_event is not None:
            self.on_event(
                ToolCallEvent(
                    worker=agent_name,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    args=args,
                    depth=self.depth,
                )
            )

    def emit_tool_result(
        self,
        agent_name: str,
        tool_name: str,
        tool_call_id: str,
        content: Any,
    ) -> None:
        """Emit a tool result event."""
        if self.on_event is not None:
            self.on_event(
                ToolResultEvent(
                    worker=agent_name,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    content=content,
                    depth=self.depth,
                )
            )


def build_path_map(mapping: Mapping[str, Path]) -> dict[str, Path]:
    """Build a path map with resolved paths."""
    resolved: dict[str, Path] = {}
    for key, value in mapping.items():
        resolved[key] = value.resolve()
    return resolved
