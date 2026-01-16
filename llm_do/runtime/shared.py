"""Shared runtime scope (config + run-scoped state)."""
from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping, Sequence, cast

from pydantic_ai.usage import RunUsage

from ..models import NULL_MODEL
from .approval import ApprovalCallback, RunApprovalPolicy, resolve_approval_callback
from .call import CallConfig, CallFrame
from .contracts import Entry, EventCallback, MessageLogCallback, ModelType
from .events import UserMessageEvent

if TYPE_CHECKING:
    from pydantic_ai.toolsets import AbstractToolset

    from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec
    from .deps import WorkerRuntime

logger = logging.getLogger(__name__)


async def cleanup_toolsets(toolsets: Sequence[Any]) -> None:
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


@asynccontextmanager
async def build_tool_plane(
    *, toolset_specs: Sequence["ToolsetSpec"], toolset_context: "ToolsetBuildContext",
    approval_callback: ApprovalCallback, return_permission_errors: bool,
) -> AsyncIterator[tuple[list["AbstractToolset[Any]"], list["AbstractToolset[Any]"]]]:
    """Instantiate and approval-wrap toolsets for a single invocation."""
    from ..toolsets.loader import instantiate_toolsets
    from .approval import wrap_toolsets_for_approval
    toolsets = instantiate_toolsets(toolset_specs, toolset_context)
    try:
        yield toolsets, wrap_toolsets_for_approval(toolsets, approval_callback, return_permission_errors=return_permission_errors)
    finally:
        await cleanup_toolsets(toolsets)


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

    def _build_entry_frame(
        self,
        entry: Entry,
        *,
        model: ModelType,
        message_history: list[Any] | None = None,
        active_toolsets: list[Any] | None = None,
    ) -> CallFrame:
        entry_name = getattr(entry, "name", str(entry))
        call_config = CallConfig(
            active_toolsets=tuple(active_toolsets or []),
            model=model,
            invocation_name=entry_name,
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
        message_history: list[Any] | None = None,
    ) -> tuple[Any, WorkerRuntime]:
        """Run an invocable with this runtime.

        Normalizes input_data to WorkerArgs for all entry types.
        Sets frame.prompt from the WorkerArgs prompt_spec().
        """
        from ..toolsets.loader import ToolsetBuildContext
        from .args import ensure_worker_args
        from .deps import WorkerRuntime
        from .worker import EntryFunction, Worker

        # Normalize input to WorkerArgs for all entries
        input_args = ensure_worker_args(invocable.schema_in, input_data)
        prompt_spec = input_args.prompt_spec()

        # Shared setup to keep Worker and EntryFunction invocation paths aligned.
        def _build_entry_context(
            entry: Entry,
            *,
            model: ModelType,
            active_toolsets: list[Any] | None = None,
        ) -> WorkerRuntime:
            frame = self._build_entry_frame(
                entry,
                model=model,
                message_history=message_history,
                active_toolsets=active_toolsets,
            )
            frame.prompt = prompt_spec.text
            ctx = WorkerRuntime(runtime=self, frame=frame)

            if self._config.on_event is not None:
                self._config.on_event(
                    UserMessageEvent(worker=entry.name, content=prompt_spec.text)
                )

            return ctx

        if isinstance(invocable, EntryFunction):
            toolset_context = invocable.toolset_context or ToolsetBuildContext(
                worker_name=invocable.name,
            )
            async with build_tool_plane(
                toolset_specs=invocable.toolset_specs,
                toolset_context=toolset_context,
                approval_callback=self._config.approval_callback,
                return_permission_errors=self._config.return_permission_errors,
            ) as (_raw_toolsets, wrapped_toolsets):
                ctx = _build_entry_context(
                    invocable,
                    model=NULL_MODEL,
                    active_toolsets=wrapped_toolsets,
                )

                # Entry functions are trusted code but still run in the tool plane.
                result = await invocable.call(input_args, ctx)
                return result, ctx

        if isinstance(invocable, Worker):
            # Worker.model is resolved during __post_init__; None is a programmer error.
            resolved_model = cast(ModelType, invocable.model)
            ctx = _build_entry_context(
                invocable,
                model=resolved_model,
                active_toolsets=[],
            )

            result = await ctx._execute(invocable, input_args)
            return result, ctx

        raise TypeError(f"Unsupported entry type: {type(invocable)}")

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
