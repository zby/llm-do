"""Worker runtime dispatcher for tools and workers.

This module provides the core runtime types used by llm-do:
- Runtime: non-entry-bound execution environment (config + state)
- RuntimeConfig: shared (structurally immutable) runtime configuration
- CallFrame: per-branch/per-worker mutable call state
- WorkerRuntime: facade over runtime+frame, used as PydanticAI deps
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, cast

from pydantic_ai.models import Model
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from ..models import select_model
from ..ui.events import UserMessageEvent
from .approval import ApprovalCallback, RunApprovalPolicy, resolve_approval_callback
from .contracts import EventCallback, Invocable, ModelType, WorkerRuntimeProtocol


class ToolsProxy:
    """Dynamic proxy to call tools by attribute name.

    Enables syntax like `ctx.tools.shell(command="ls")` to invoke tools.
    """

    def __init__(self, ctx: "WorkerRuntime") -> None:
        self._ctx = ctx

    def __getattr__(self, name: str) -> Callable[..., Awaitable[Any]]:
        async def _call(**kwargs: Any) -> Any:
            return await self._ctx.call(name, kwargs)

        return _call

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
        message_history: Optional[list[Any]] = None,
    ) -> "CallFrame":
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
    ) -> tuple[Any, "WorkerRuntime"]:
        """Run an invocable with this runtime."""
        frame = self._build_entry_frame(invocable, model=model, message_history=message_history)
        ctx = WorkerRuntime(runtime=self, frame=frame)
        input_data: dict[str, str] = {"input": prompt}

        if self._config.on_event is not None:
            self._config.on_event(UserMessageEvent(worker=invocable.name, content=prompt))

        result = await ctx.run(invocable, input_data)
        return result, ctx


@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""

    toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0


@dataclass(slots=True)
class CallFrame:
    """Per-worker call state with immutable config and mutable conversation state."""

    config: CallConfig

    # Mutable fields (required for runtime behavior)
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    # Convenience accessors for backward compatibility
    @property
    def toolsets(self) -> tuple[AbstractToolset[Any], ...]:
        return self.config.toolsets

    @property
    def model(self) -> ModelType:
        return self.config.model

    @property
    def depth(self) -> int:
        return self.config.depth

    def fork(
        self,
        toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
    ) -> "CallFrame":
        """Create child frame with incremented depth and fresh messages."""
        new_config = CallConfig(
            toolsets=tuple(toolsets) if toolsets is not None else self.config.toolsets,
            model=model if model is not None else self.config.model,
            depth=self.config.depth + 1,
        )
        return CallFrame(config=new_config)


class WorkerRuntime:
    """Dispatches tool calls and manages worker runtime state.

    WorkerRuntime is the central orchestrator for executing tools and workers.
    It holds:
    - runtime (Runtime): shared config and runtime-scoped state
    - per-branch state (CallFrame): depth, prompt/messages, toolsets, effective model
    """

    @classmethod
    def from_entry(
        cls,
        entry: "Invocable",
        model: ModelType | None = None,
        *,
        run_approval_policy: RunApprovalPolicy | None = None,
        max_depth: int = 5,
        messages: Optional[list[Any]] = None,
        on_event: Optional[EventCallback] = None,
        verbosity: int = 0,
    ) -> "WorkerRuntime":
        """Create a WorkerRuntime for running an entry.

        Args:
            entry: The entry to run (Worker or ToolInvocable)
            model: Model override (uses entry.model if not provided)
            max_depth: Maximum call depth
            messages: Optional message history for multi-turn conversations
            on_event: Optional callback for UI events (tool calls, streaming text)
            verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)

        Returns:
            WorkerRuntime configured for the entry
        """
        runtime = Runtime(
            cli_model=model,
            run_approval_policy=run_approval_policy,
            max_depth=max_depth,
            on_event=on_event,
            verbosity=verbosity,
        )
        frame = runtime._build_entry_frame(entry, model=model, message_history=messages)
        return cls(runtime=runtime, frame=frame)

    def __init__(
        self,
        toolsets: list[AbstractToolset[Any]] | None = None,
        model: ModelType | None = None,
        *,
        runtime: Runtime | None = None,
        frame: CallFrame | None = None,
        cli_model: ModelType | None = None,
        run_approval_policy: RunApprovalPolicy | None = None,
        max_depth: int = 5,
        depth: int = 0,
        prompt: str = "",
        messages: Optional[list[Any]] = None,
        on_event: Optional[EventCallback] = None,
        verbosity: int = 0,
    ) -> None:
        if runtime is not None or frame is not None:
            if runtime is None or frame is None:
                raise TypeError("WorkerRuntime requires both 'runtime' and 'frame' when either is provided")
            self.runtime = runtime
            self.frame = frame
        else:
            if toolsets is None or model is None:
                raise TypeError("WorkerRuntime requires 'toolsets' and 'model' when 'runtime'/'frame' are not provided")
            self.runtime = Runtime(
                cli_model=cli_model,
                run_approval_policy=run_approval_policy or RunApprovalPolicy(mode="approve_all"),
                max_depth=max_depth,
                on_event=on_event,
                verbosity=verbosity,
            )
            call_config = CallConfig(
                toolsets=tuple(toolsets),
                model=model,
                depth=depth,
            )
            self.frame = CallFrame(
                config=call_config,
                prompt=prompt,
                messages=messages if messages is not None else [],
            )
        self.tools = ToolsProxy(self)

    @property
    def config(self) -> RuntimeConfig:
        return self.runtime.config

    @property
    def approval_callback(self) -> ApprovalCallback:
        return self.runtime.approval_callback

    @property
    def toolsets(self) -> tuple[AbstractToolset[Any], ...]:
        return self.frame.toolsets

    @property
    def model(self) -> ModelType:
        return self.frame.model

    @property
    def cli_model(self) -> ModelType | None:
        return self.runtime.config.cli_model

    @property
    def run_approval_policy(self) -> RunApprovalPolicy:
        return self.runtime.config.run_approval_policy

    @property
    def max_depth(self) -> int:
        return self.runtime.config.max_depth

    @property
    def depth(self) -> int:
        return self.frame.depth

    @property
    def prompt(self) -> str:
        return self.frame.prompt

    @prompt.setter
    def prompt(self, value: str) -> None:
        self.frame.prompt = value

    @property
    def messages(self) -> list[Any]:
        return self.frame.messages

    @property
    def on_event(self) -> EventCallback | None:
        return self.runtime.config.on_event

    @property
    def verbosity(self) -> int:
        return self.runtime.config.verbosity

    @property
    def usage(self) -> list[RunUsage]:
        return self.runtime.usage

    @property
    def message_log(self) -> list[tuple[str, int, Any]]:
        """Return all messages captured across all workers (for testing/logging)."""
        return self.runtime.message_log

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(worker_name, depth, messages)

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self.runtime._create_usage()

    def _make_run_context(
        self, tool_name: str, resolved_model: ModelType, deps_ctx: WorkerRuntimeProtocol
    ) -> RunContext[WorkerRuntimeProtocol]:
        """Construct a RunContext for direct tool invocation."""
        return RunContext(
            deps=deps_ctx,
            model=cast(Model, resolved_model),
            usage=self._create_usage(),
            prompt=deps_ctx.prompt,
            messages=list(deps_ctx.messages),
            run_step=deps_ctx.depth,
            retry=0,
            tool_name=tool_name,
        )

    def spawn_child(
        self,
        toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
    ) -> "WorkerRuntime":
        """Spawn a child worker runtime with a forked CallFrame (depth+1)."""
        return WorkerRuntime(
            runtime=self.runtime,
            frame=self.frame.fork(toolsets, model=model),
        )

    async def run(self, entry: Invocable, input_data: Any) -> Any:
        """Run an entry directly."""
        # Extract prompt from input_data for RunContext
        if isinstance(input_data, dict) and "input" in input_data:
            self.prompt = str(input_data["input"])
        elif isinstance(input_data, str):
            self.prompt = input_data
        return await self._execute(entry, input_data)

    async def call(self, name: str, input_data: Any) -> Any:
        """Call a tool by name (searched across toolsets).

        This enables programmatic tool invocation from code entry points:
            result = await ctx.deps.call("pitch_evaluator", {"input": "..."})
        """
        import uuid

        from ..ui.events import ToolCallEvent, ToolResultEvent

        # Create a temporary run context for get_tools
        run_ctx = self._make_run_context(name, self.model, self)

        # Search for the tool across all toolsets
        for toolset in self.toolsets:
            tools = await toolset.get_tools(run_ctx)
            if name in tools:
                tool = tools[name]

                # Generate a unique call ID for event correlation
                call_id = str(uuid.uuid4())[:8]

                # Emit ToolCallEvent before execution
                if self.on_event is not None:
                    self.on_event(
                        ToolCallEvent(
                            worker="code_entry",
                            tool_name=name,
                            tool_call_id=call_id,
                            args=input_data,
                        )
                    )

                # Execute the tool
                result = await toolset.call_tool(name, input_data, run_ctx, tool)

                # Emit ToolResultEvent after execution
                if self.on_event is not None:
                    self.on_event(
                        ToolResultEvent(
                            worker="code_entry",
                            tool_name=name,
                            tool_call_id=call_id,
                            content=result,
                        )
                    )

                return result

        available: list[str] = []
        for toolset in self.toolsets:
            tools = await toolset.get_tools(run_ctx)
            available.extend(tools.keys())
        raise KeyError(f"Tool '{name}' not found. Available: {available}")

    async def _execute(self, entry: Invocable, input_data: Any) -> Any:
        """Execute an entry.

        The entry's call() method is responsible for creating any child context
        it needs. Worker.call() creates a child with wrapped toolsets and
        incremented depth. ToolInvocable.call() uses the run_ctx directly.

        Uses two-object API: passes config (global) and frame (per-call) separately.
        """
        run_ctx = self._make_run_context(entry.name, self.model, self)
        return await entry.call(input_data, self.config, self.frame, run_ctx)
