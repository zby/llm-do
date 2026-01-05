"""Worker runtime dispatcher for tools and workers.

This module provides the core runtime types used by llm-do:
- RuntimeConfig: shared (structurally immutable) runtime configuration
- CallFrame: per-branch/per-worker mutable call state
- WorkerRuntime: facade over config+frame, used as PydanticAI deps
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
from .approval import RunApprovalPolicy
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


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Shared runtime configuration (no per-call-chain state)."""

    cli_model: ModelType | None
    run_approval_policy: RunApprovalPolicy
    max_depth: int = 5
    on_event: EventCallback | None = None
    verbosity: int = 0
    usage: UsageCollector = field(default_factory=UsageCollector)


@dataclass(slots=True)
class CallFrame:
    """Per-branch/per-worker call state (forked on spawn)."""

    toolsets: list[AbstractToolset[Any]]
    model: ModelType
    depth: int = 0
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    def fork(
        self,
        toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
    ) -> "CallFrame":
        return CallFrame(
            toolsets=self.toolsets if toolsets is None else toolsets,
            model=self.model if model is None else model,
            depth=self.depth + 1,
            prompt=self.prompt,
            messages=[],
        )

    def clone_same_depth(
        self,
        toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
    ) -> "CallFrame":
        return CallFrame(
            toolsets=self.toolsets if toolsets is None else toolsets,
            model=self.model if model is None else model,
            depth=self.depth,
            prompt=self.prompt,
            messages=self.messages,
        )


class WorkerRuntime:
    """Dispatches tool calls and manages worker runtime state.

    WorkerRuntime is the central orchestrator for executing tools and workers.
    It holds:
    - shared config (RuntimeConfig): model resolution inputs, events, usage sink
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
        # Resolve model using model_compat module
        entry_name = getattr(entry, "name", str(entry))
        resolved_model = select_model(
            worker_model=getattr(entry, "model", None),
            cli_model=model,
            compatible_models=getattr(entry, "compatible_models", None),
            worker_name=entry_name,
        )

        # Get toolsets from entry
        toolsets = list(getattr(entry, "toolsets", []) or [])

        config = RuntimeConfig(
            cli_model=model,
            run_approval_policy=run_approval_policy or RunApprovalPolicy(mode="approve_all"),
            max_depth=max_depth,
            on_event=on_event,
            verbosity=verbosity,
        )
        frame = CallFrame(
            toolsets=toolsets,
            model=resolved_model,
            messages=messages if messages is not None else [],
        )
        return cls(config=config, frame=frame)

    def __init__(
        self,
        toolsets: list[AbstractToolset[Any]] | None = None,
        model: ModelType | None = None,
        *,
        config: RuntimeConfig | None = None,
        frame: CallFrame | None = None,
        cli_model: ModelType | None = None,
        run_approval_policy: RunApprovalPolicy | None = None,
        max_depth: int = 5,
        depth: int = 0,
        prompt: str = "",
        messages: Optional[list[Any]] = None,
        on_event: Optional[EventCallback] = None,
        verbosity: int = 0,
        usage: UsageCollector | None = None,
    ) -> None:
        if config is not None or frame is not None:
            if config is None or frame is None:
                raise TypeError("WorkerRuntime requires both 'config' and 'frame' when either is provided")
            self.config = config
            self.frame = frame
        else:
            if toolsets is None or model is None:
                raise TypeError("WorkerRuntime requires 'toolsets' and 'model' when 'config'/'frame' are not provided")
            runtime_usage = usage or UsageCollector()
            self.config = RuntimeConfig(
                cli_model=cli_model,
                run_approval_policy=run_approval_policy or RunApprovalPolicy(mode="approve_all"),
                max_depth=max_depth,
                on_event=on_event,
                verbosity=verbosity,
                usage=runtime_usage,
            )
            self.frame = CallFrame(
                toolsets=toolsets,
                model=model,
                depth=depth,
                prompt=prompt,
                messages=messages if messages is not None else [],
            )
        self.tools = ToolsProxy(self)

    @property
    def toolsets(self) -> list[AbstractToolset[Any]]:
        return self.frame.toolsets

    @property
    def model(self) -> ModelType:
        return self.frame.model

    @property
    def cli_model(self) -> ModelType | None:
        return self.config.cli_model

    @property
    def run_approval_policy(self) -> RunApprovalPolicy:
        return self.config.run_approval_policy

    @property
    def max_depth(self) -> int:
        return self.config.max_depth

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
        return self.config.on_event

    @property
    def verbosity(self) -> int:
        return self.config.verbosity

    @property
    def usage(self) -> list[RunUsage]:
        return self.config.usage.all()

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self.config.usage.create()

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
            config=self.config,
            frame=self.frame.fork(toolsets, model=model),
        )

    def clone_same_depth(
        self,
        toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
    ) -> "WorkerRuntime":
        """Create a runtime copy without changing depth (shares CallFrame messages)."""
        return WorkerRuntime(
            config=self.config,
            frame=self.frame.clone_same_depth(toolsets, model=model),
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
        """
        run_ctx = self._make_run_context(entry.name, self.model, self)
        return await entry.call(input_data, self, run_ctx)
