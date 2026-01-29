"""Shared runtime scope (config + run-scoped state)."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from pydantic_ai.usage import RunUsage

from ..models import ModelInput, resolve_model
from ..toolsets.loader import ToolsetSpec
from .approval import ApprovalCallback, RunApprovalPolicy, resolve_approval_callback
from .contracts import (
    AgentSpec,
    Entry,
    EventCallback,
    MessageLogCallback,
)

if TYPE_CHECKING:
    from .context import CallContext
    from .registry import AgentRegistry


class UsageCollector:
    """Thread-safe sink for RunUsage objects."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usages: list[RunUsage] = []

    def create(self) -> RunUsage:
        usage = RunUsage()
        with self._lock:
            self._usages.append(usage)
        return usage

    def all(self) -> list[RunUsage]:
        with self._lock:
            return list(self._usages)


class MessageAccumulator:
    """Thread-safe sink for capturing messages across agents."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: list[tuple[str, int, Any]] = []

    def append(self, agent_name: str, depth: int, message: Any) -> None:
        with self._lock:
            self._messages.append((agent_name, depth, message))

    def extend(self, agent_name: str, depth: int, messages: list[Any]) -> None:
        with self._lock:
            self._messages.extend((agent_name, depth, msg) for msg in messages)

    def all(self) -> list[tuple[str, int, Any]]:
        with self._lock:
            return list(self._messages)

    def for_agent(self, agent_name: str) -> list[Any]:
        with self._lock:
            return [msg for name, _, msg in self._messages if name == agent_name]


@dataclass(frozen=True, slots=True)
class AgentApprovalConfig:
    """Per-agent approval overrides."""
    calls_require_approval: bool | None = None
    attachments_require_approval: bool | None = None


def _normalize_agent_approval_overrides(overrides: Mapping[str, Any] | None) -> dict[str, AgentApprovalConfig]:
    if not overrides:
        return {}
    normalized: dict[str, AgentApprovalConfig] = {}
    for name, value in overrides.items():
        if isinstance(value, AgentApprovalConfig):
            normalized[name] = value
        elif hasattr(value, "model_dump"):
            value = value.model_dump()
            normalized[name] = AgentApprovalConfig(calls_require_approval=value.get("calls_require_approval"), attachments_require_approval=value.get("attachments_require_approval"))
        elif isinstance(value, Mapping):
            normalized[name] = AgentApprovalConfig(calls_require_approval=value.get("calls_require_approval"), attachments_require_approval=value.get("attachments_require_approval"))
        else:
            raise TypeError("agent_approval_overrides values must be mappings or AgentApprovalConfig")
    return normalized


def _resolve_generated_agents_dir(
    value: str | Path | None,
    project_root: Path | None,
) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        base = project_root or Path.cwd()
        return (base / path).resolve()
    return path.resolve()


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Shared runtime configuration."""
    approval_callback: ApprovalCallback
    project_root: Path | None = None
    return_permission_errors: bool = False
    max_depth: int = 5
    generated_agents_dir: Path | None = None
    agent_calls_require_approval: bool = False
    agent_attachments_require_approval: bool = False
    agent_approval_overrides: dict[str, AgentApprovalConfig] = field(default_factory=dict)
    on_event: EventCallback | None = None
    message_log_callback: MessageLogCallback | None = None
    verbosity: int = 0


class Runtime:
    """Non-entry-bound execution environment shared across runs."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        run_approval_policy: RunApprovalPolicy | None = None,
        max_depth: int = 5,
        generated_agents_dir: str | Path | None = None,
        agent_calls_require_approval: bool = False,
        agent_attachments_require_approval: bool = False,
        agent_approval_overrides: Mapping[str, Any] | None = None,
        on_event: EventCallback | None = None,
        message_log_callback: MessageLogCallback | None = None,
        verbosity: int = 0,
    ) -> None:
        policy = run_approval_policy or RunApprovalPolicy(mode="approve_all")
        resolved_generated_dir = _resolve_generated_agents_dir(
            generated_agents_dir, project_root
        )
        approval_callback = resolve_approval_callback(policy)
        self._config = RuntimeConfig(
            approval_callback=approval_callback,
            project_root=project_root,
            return_permission_errors=policy.return_permission_errors,
            max_depth=max_depth,
            generated_agents_dir=resolved_generated_dir,
            agent_calls_require_approval=agent_calls_require_approval,
            agent_attachments_require_approval=agent_attachments_require_approval,
            agent_approval_overrides=_normalize_agent_approval_overrides(
                agent_approval_overrides
            ),
            on_event=on_event,
            message_log_callback=message_log_callback,
            verbosity=verbosity,
        )
        self._usage = UsageCollector()
        self._message_log = MessageAccumulator()
        self._agent_registry: dict[str, AgentSpec] = {}
        self._toolset_registry: dict[str, ToolsetSpec] = {}
        self._dynamic_agents: dict[str, AgentSpec] = {}

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    @property
    def project_root(self) -> Path | None:
        return self._config.project_root

    @property
    def approval_callback(self) -> ApprovalCallback:
        return self._config.approval_callback

    @property
    def usage(self) -> list[RunUsage]:
        return self._usage.all()

    @property
    def message_log(self) -> list[tuple[str, int, Any]]:
        return self._message_log.all()

    @property
    def agent_registry(self) -> dict[str, AgentSpec]:
        return self._agent_registry

    @property
    def toolset_registry(self) -> dict[str, ToolsetSpec]:
        return self._toolset_registry

    @property
    def dynamic_agents(self) -> dict[str, AgentSpec]:
        return self._dynamic_agents

    def register_agents(self, agents: Mapping[str, AgentSpec]) -> None:
        self._agent_registry = dict(agents)

    def register_toolsets(self, toolsets: Mapping[str, ToolsetSpec]) -> None:
        self._toolset_registry = dict(toolsets)

    def register_registry(self, registry: "AgentRegistry") -> None:
        self.register_agents(registry.agents)
        self.register_toolsets(registry.toolsets)

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self._usage.create()

    def log_messages(self, agent_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self._message_log.extend(agent_name, depth, messages)
        if self._config.message_log_callback is not None:
            self._config.message_log_callback(agent_name, depth, messages)

    def spawn_call_runtime(
        self,
        active_toolsets: Sequence[Any],
        *,
        model: ModelInput,
        invocation_name: str,
        depth: int,
    ) -> "CallContext":
        """Create a CallContext with a new CallFrame."""
        from .call import CallConfig, CallFrame
        from .context import CallContext

        resolved_model = resolve_model(model)
        call_config = CallConfig.build(
            active_toolsets,
            model=resolved_model,
            depth=depth,
            invocation_name=invocation_name,
        )
        frame = CallFrame(config=call_config)
        return CallContext(runtime=self, frame=frame)

    async def run_entry(
        self,
        entry: Entry,
        input_data: Any,
        *,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, CallContext]:
        """Run an entry with this runtime."""
        from ..models import NULL_MODEL
        from .args import get_display_text, normalize_input
        from .events import RuntimeEvent, UserMessageEvent

        input_args, messages = normalize_input(entry.input_model, input_data)
        display_text = get_display_text(messages)
        if self.config.on_event is not None:
            self.config.on_event(
                RuntimeEvent(
                    worker=entry.name,
                    depth=0,
                    event=UserMessageEvent(content=display_text),
                )
            )

        call_runtime = self.spawn_call_runtime(
            active_toolsets=[],
            model=NULL_MODEL,
            invocation_name=entry.name,
            depth=0,
        )
        if message_history:
            call_runtime.frame.messages[:] = list(message_history)
        call_runtime.frame.prompt = display_text

        result = await entry.run(input_args, call_runtime)

        return result, call_runtime

    def run(
        self,
        entry: Entry,
        input_data: Any,
        *,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, "CallContext"]:
        """Run an invocable synchronously using asyncio.run()."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "Runtime.run() cannot be called from a running event loop; "
                "use Runtime.run_entry() instead."
            )

        return asyncio.run(
            self.run_entry(
                entry,
                input_data,
                message_history=message_history,
            )
        )
