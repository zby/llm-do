"""Shared runtime scope (config + run-scoped state)."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai.usage import RunUsage

from ..models import select_model
from ..ui.events import UserMessageEvent
from .approval import ApprovalCallback, RunApprovalPolicy, resolve_approval_callback
from .call import CallConfig, CallFrame
from .contracts import EventCallback, Invocable, ModelType

if TYPE_CHECKING:
    from .deps import WorkerRuntime
    from .registry import InvocableRegistry


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
    """Thread-safe sink for capturing messages across all workers.

    Used for testing and logging. Workers do NOT read from this
    for their conversation context - that stays in CallFrame.messages.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: list[tuple[str, int, Any]] = []  # (worker_name, depth, message)

    def append(self, worker_name: str, depth: int, message: Any) -> None:
        """Record a message from a worker."""
        with self._lock:
            self._messages.append((worker_name, depth, message))

    def extend(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record multiple messages from a worker."""
        with self._lock:
            for msg in messages:
                self._messages.append((worker_name, depth, msg))

    def all(self) -> list[tuple[str, int, Any]]:
        """Return all recorded messages."""
        with self._lock:
            return list(self._messages)

    def for_worker(self, worker_name: str) -> list[Any]:
        """Return messages for a specific worker."""
        with self._lock:
            return [msg for name, _, msg in self._messages if name == worker_name]


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Shared runtime configuration (no per-call-chain state)."""

    cli_model: ModelType | None
    run_approval_policy: RunApprovalPolicy
    max_depth: int = 5
    on_event: EventCallback | None = None
    verbosity: int = 0


class Runtime:
    """Non-entry-bound execution environment shared across runs."""

    def __init__(
        self,
        *,
        cli_model: ModelType | None = None,
        run_approval_policy: RunApprovalPolicy | None = None,
        max_depth: int = 5,
        on_event: EventCallback | None = None,
        verbosity: int = 0,
    ) -> None:
        policy = run_approval_policy or RunApprovalPolicy(mode="approve_all")
        self._config = RuntimeConfig(
            cli_model=cli_model,
            run_approval_policy=policy,
            max_depth=max_depth,
            on_event=on_event,
            verbosity=verbosity,
        )
        self._usage = UsageCollector()
        self._message_log = MessageAccumulator()
        self._approval_callback = resolve_approval_callback(policy)

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    @property
    def approval_callback(self) -> ApprovalCallback:
        return self._approval_callback

    @property
    def usage(self) -> list[RunUsage]:
        return self._usage.all()

    @property
    def message_log(self) -> list[tuple[str, int, Any]]:
        return self._message_log.all()

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self._usage.create()

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self._message_log.extend(worker_name, depth, messages)

    def _build_entry_frame(
        self,
        entry: Invocable,
        *,
        model: ModelType | None = None,
        message_history: list[Any] | None = None,
    ) -> CallFrame:
        entry_name = getattr(entry, "name", str(entry))
        resolved_model = select_model(
            worker_model=getattr(entry, "model", None),
            cli_model=model if model is not None else self._config.cli_model,
            compatible_models=getattr(entry, "compatible_models", None),
            worker_name=entry_name,
        )
        toolsets = list(getattr(entry, "toolsets", []) or [])
        call_config = CallConfig(
            toolsets=tuple(toolsets),
            model=resolved_model,
        )
        return CallFrame(
            config=call_config,
            messages=list(message_history) if message_history else [],
        )

    async def run_invocable(
        self,
        invocable: Invocable,
        prompt: str,
        *,
        model: ModelType | None = None,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, WorkerRuntime]:
        """Run an invocable with this runtime."""
        from .deps import WorkerRuntime

        frame = self._build_entry_frame(invocable, model=model, message_history=message_history)
        ctx = WorkerRuntime(runtime=self, frame=frame)
        input_data: dict[str, str] = {"input": prompt}

        if self._config.on_event is not None:
            self._config.on_event(UserMessageEvent(worker=invocable.name, content=prompt))

        result = await ctx.run(invocable, input_data)
        return result, ctx

    async def run_entry(
        self,
        registry: "InvocableRegistry",
        entry_name: str,
        prompt: str,
        *,
        model: ModelType | None = None,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, WorkerRuntime]:
        """Run a registry entry by name with this runtime."""
        invocable = registry.get(entry_name)
        return await self.run_invocable(
            invocable,
            prompt,
            model=model,
            message_history=message_history,
        )

    def run(
        self,
        invocable: Invocable,
        prompt: str,
        *,
        model: ModelType | None = None,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, "WorkerRuntime"]:
        """Run an invocable synchronously using asyncio.run()."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "Runtime.run() cannot be called from a running event loop; "
                "use Runtime.run_invocable() instead."
            )

        return asyncio.run(
            self.run_invocable(
                invocable,
                prompt,
                model=model,
                message_history=message_history,
            )
        )

    def run_entry_sync(
        self,
        registry: "InvocableRegistry",
        entry_name: str,
        prompt: str,
        *,
        model: ModelType | None = None,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, "WorkerRuntime"]:
        """Run a registry entry synchronously using asyncio.run()."""
        return self.run(
            registry.get(entry_name),
            prompt,
            model=model,
            message_history=message_history,
        )
