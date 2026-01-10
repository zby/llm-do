"""Runtime deps facade for tool execution."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, cast

from pydantic import BaseModel
from pydantic_ai.models import Model
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from .approval import ApprovalCallback, RunApprovalPolicy
from .call import CallConfig, CallFrame
from .contracts import EventCallback, Invocable, ModelType, WorkerRuntimeProtocol
from .shared import Runtime, RuntimeConfig


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

    def _validate_tool_args(
        self,
        toolset: AbstractToolset[Any],
        tool: Any,
        input_data: Any,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any:
        """Validate tool args for direct calls to match PydanticAI behavior."""
        args = input_data
        if isinstance(args, BaseModel):
            args = args.model_dump()

        from .input_utils import coerce_worker_input
        from .worker import Worker

        if isinstance(toolset, Worker):
            args = coerce_worker_input(toolset.schema_in, args)

        validator = tool.args_validator
        if isinstance(args, (str, bytes, bytearray)):
            json_input = args if args else "{}"
            return validator.validate_json(
                json_input,
                allow_partial="off",
                context=run_ctx.validation_context,
            )

        if args is None:
            args = {}
        return validator.validate_python(
            args,
            allow_partial="off",
            context=run_ctx.validation_context,
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
                validated_args = self._validate_tool_args(
                    toolset,
                    tool,
                    input_data,
                    run_ctx,
                )

                # Generate a unique call ID for event correlation
                call_id = str(uuid.uuid4())[:8]

                # Emit ToolCallEvent before execution
                if self.on_event is not None:
                    self.on_event(
                        ToolCallEvent(
                            worker="code_entry",
                            tool_name=name,
                            tool_call_id=call_id,
                            args=validated_args,
                            depth=self.depth,
                        )
                    )

                # Execute the tool
                result = await toolset.call_tool(name, validated_args, run_ctx, tool)

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
