"""Shared runtime scope (config + run-scoped state)."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, cast

from pydantic_ai.usage import RunUsage

from .approval import ApprovalCallback, RunApprovalPolicy, resolve_approval_callback
from .contracts import Entry, EventCallback, MessageLogCallback

if TYPE_CHECKING:
    from .deps import WorkerRuntime


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
    """Thread-safe sink for capturing messages across workers."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: list[tuple[str, int, Any]] = []

    def append(self, worker_name: str, depth: int, message: Any) -> None:
        with self._lock:
            self._messages.append((worker_name, depth, message))

    def extend(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        with self._lock:
            self._messages.extend((worker_name, depth, msg) for msg in messages)

    def all(self) -> list[tuple[str, int, Any]]:
        with self._lock:
            return list(self._messages)

    def for_worker(self, worker_name: str) -> list[Any]:
        with self._lock:
            return [msg for name, _, msg in self._messages if name == worker_name]


@dataclass(frozen=True, slots=True)
class WorkerApprovalConfig:
    """Per-worker approval overrides."""
    calls_require_approval: bool | None = None
    attachments_require_approval: bool | None = None


def _normalize_worker_approval_overrides(overrides: Mapping[str, Any] | None) -> dict[str, WorkerApprovalConfig]:
    if not overrides:
        return {}
    normalized: dict[str, WorkerApprovalConfig] = {}
    for name, value in overrides.items():
        if isinstance(value, WorkerApprovalConfig):
            normalized[name] = value
        elif hasattr(value, "model_dump"):
            value = value.model_dump()
            normalized[name] = WorkerApprovalConfig(calls_require_approval=value.get("calls_require_approval"), attachments_require_approval=value.get("attachments_require_approval"))
        elif isinstance(value, Mapping):
            normalized[name] = WorkerApprovalConfig(calls_require_approval=value.get("calls_require_approval"), attachments_require_approval=value.get("attachments_require_approval"))
        else:
            raise TypeError("worker_approval_overrides values must be mappings or WorkerApprovalConfig")
    return normalized


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Shared runtime configuration."""
    approval_callback: ApprovalCallback
    project_root: Path | None = None
    return_permission_errors: bool = False
    max_depth: int = 5
    worker_calls_require_approval: bool = False
    worker_attachments_require_approval: bool = False
    worker_approval_overrides: dict[str, WorkerApprovalConfig] = field(default_factory=dict)
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
        worker_calls_require_approval: bool = False,
        worker_attachments_require_approval: bool = False,
        worker_approval_overrides: Mapping[str, Any] | None = None,
        on_event: EventCallback | None = None,
        message_log_callback: MessageLogCallback | None = None,
        verbosity: int = 0,
    ) -> None:
        policy = run_approval_policy or RunApprovalPolicy(mode="approve_all")
        approval_callback = resolve_approval_callback(policy)
        self._config = RuntimeConfig(
            approval_callback=approval_callback,
            project_root=project_root,
            return_permission_errors=policy.return_permission_errors,
            max_depth=max_depth,
            worker_calls_require_approval=worker_calls_require_approval,
            worker_attachments_require_approval=worker_attachments_require_approval,
            worker_approval_overrides=_normalize_worker_approval_overrides(
                worker_approval_overrides
            ),
            on_event=on_event,
            message_log_callback=message_log_callback,
            verbosity=verbosity,
        )
        self._usage = UsageCollector()
        self._message_log = MessageAccumulator()

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

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self._usage.create()

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self._message_log.extend(worker_name, depth, messages)
        if self._config.message_log_callback is not None:
            self._config.message_log_callback(worker_name, depth, messages)

    async def run_entry(
        self,
        invocable: Entry,
        input_data: Any,
        *,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, WorkerRuntime]:
        """Run an invocable with this runtime.

        Entry implementations handle per-turn prompt handling inside run_turn.
        """
        from .deps import WorkerRuntime
        try:
            scope = invocable.start(self, message_history=message_history)
        except AttributeError as exc:
            raise TypeError(f"Unsupported entry type: {type(invocable)}") from exc

        async with scope:
            result = await scope.run_turn(input_data)
        return result, cast(WorkerRuntime, scope.runtime)

    def run(
        self,
        invocable: Entry,
        input_data: Any,
        *,
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
                "use Runtime.run_entry() instead."
            )

        return asyncio.run(
            self.run_entry(
                invocable,
                input_data,
                message_history=message_history,
            )
        )
