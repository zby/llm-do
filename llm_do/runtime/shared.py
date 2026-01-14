"""Shared runtime scope (config + run-scoped state)."""
from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from pydantic_ai.usage import RunUsage

from ..models import select_model
from ..ui.events import UserMessageEvent
from .approval import ApprovalCallback, RunApprovalPolicy, resolve_approval_callback
from .call import CallConfig, CallFrame
from .contracts import Entry, EventCallback, MessageLogCallback, ModelType

if TYPE_CHECKING:
    from .deps import WorkerRuntime

logger = logging.getLogger(__name__)

async def cleanup_toolsets(toolsets: Sequence[Any]) -> None:
    """Run cleanup hooks on toolsets, ignoring errors."""
    for toolset in toolsets:
        cleanup = getattr(toolset, "cleanup", None)
        if cleanup is None:
            continue
        try:
            result = cleanup()
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("Toolset cleanup failed for %r", toolset)


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
    approval_callback: ApprovalCallback
    project_root: Path | None = None
    return_permission_errors: bool = False
    max_depth: int = 5
    on_event: EventCallback | None = None
    message_log_callback: MessageLogCallback | None = None
    verbosity: int = 0


class Runtime:
    """Non-entry-bound execution environment shared across runs."""

    def __init__(
        self,
        *,
        cli_model: ModelType | None = None,
        project_root: Path | None = None,
        run_approval_policy: RunApprovalPolicy | None = None,
        max_depth: int = 5,
        on_event: EventCallback | None = None,
        message_log_callback: MessageLogCallback | None = None,
        verbosity: int = 0,
    ) -> None:
        policy = run_approval_policy or RunApprovalPolicy(mode="approve_all")
        approval_callback = resolve_approval_callback(policy)
        self._config = RuntimeConfig(
            cli_model=cli_model,
            approval_callback=approval_callback,
            project_root=project_root,
            return_permission_errors=policy.return_permission_errors,
            max_depth=max_depth,
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

    def _build_entry_frame(
        self,
        entry: Entry,
        *,
        model: ModelType | None = None,
        message_history: list[Any] | None = None,
        active_toolsets: list[Any] | None = None,
    ) -> CallFrame:
        entry_name = getattr(entry, "name", str(entry))
        resolved_model = select_model(
            worker_model=getattr(entry, "model", None),
            cli_model=model if model is not None else self._config.cli_model,
            compatible_models=getattr(entry, "compatible_models", None),
            worker_name=entry_name,
        )
        call_config = CallConfig(
            active_toolsets=tuple(active_toolsets or []),
            model=resolved_model,
        )
        return CallFrame(
            config=call_config,
            messages=list(message_history) if message_history else [],
        )

    async def run_entry(
        self,
        invocable: Entry,
        input_data: Any,
        *,
        model: ModelType | None = None,
        message_history: list[Any] | None = None,
    ) -> tuple[Any, WorkerRuntime]:
        """Run an invocable with this runtime.

        Normalizes input_data to WorkerArgs for all entry types.
        Sets frame.prompt from the WorkerArgs prompt_spec().
        """
        from ..toolsets.loader import ToolsetBuildContext, instantiate_toolsets
        from .args import ensure_worker_args
        from .deps import WorkerRuntime
        from .worker import EntryFunction, Worker

        # Normalize input to WorkerArgs for all entries
        input_args = ensure_worker_args(invocable.schema_in, input_data)
        prompt_spec = input_args.prompt_spec()

        toolsets: list[Any] = []
        if isinstance(invocable, EntryFunction):
            toolset_context = invocable.toolset_context or ToolsetBuildContext(
                worker_name=invocable.name,
            )
            toolsets = instantiate_toolsets(invocable.toolset_specs, toolset_context)

        frame = self._build_entry_frame(
            invocable,
            model=model,
            message_history=message_history,
            active_toolsets=toolsets,
        )
        frame.prompt = prompt_spec.text
        ctx = WorkerRuntime(runtime=self, frame=frame)

        if self._config.on_event is not None:
            self._config.on_event(
                UserMessageEvent(worker=invocable.name, content=prompt_spec.text)
            )

        try:
            if isinstance(invocable, EntryFunction):
                # Entry functions are trusted code; tool calls run directly without approval wrappers.
                result = await invocable.call(input_args, ctx)
            elif isinstance(invocable, Worker):
                result = await ctx._execute(invocable, input_args)
            else:
                raise TypeError(f"Unsupported entry type: {type(invocable)}")
            return result, ctx
        finally:
            await cleanup_toolsets(toolsets)

    def run(
        self,
        invocable: Entry,
        input_data: Any,
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
                "use Runtime.run_entry() instead."
            )

        return asyncio.run(
            self.run_entry(
                invocable,
                input_data,
                model=model,
                message_history=message_history,
            )
        )
