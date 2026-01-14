"""Runtime deps facade for tool execution."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from pydantic import BaseModel
from pydantic_ai.models import Model, infer_model
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from .approval import ApprovalCallback
from .args import WorkerArgs, ensure_worker_args
from .call import CallFrame
from .contracts import EventCallback, ModelType, WorkerRuntimeProtocol

if TYPE_CHECKING:
    from .worker import Worker

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

    def __init__(
        self,
        *,
        runtime: Runtime,
        frame: CallFrame,
    ) -> None:
        self.runtime = runtime
        self.frame = frame
        self.tools = ToolsProxy(self)

    @property
    def config(self) -> RuntimeConfig:
        return self.runtime.config

    @property
    def project_root(self) -> Path | None:
        return self.runtime.project_root

    @property
    def approval_callback(self) -> ApprovalCallback:
        return self.runtime.approval_callback

    @property
    def active_toolsets(self) -> tuple[AbstractToolset[Any], ...]:
        """Toolsets available for this call (with approval wrappers applied)."""
        return self.frame.active_toolsets

    @property
    def model(self) -> ModelType:
        return self.frame.model

    @property
    def cli_model(self) -> ModelType | None:
        return self.runtime.config.cli_model

    @property
    def return_permission_errors(self) -> bool:
        return self.runtime.config.return_permission_errors

    @property
    def max_depth(self) -> int:
        return self.runtime.config.max_depth

    @property
    def depth(self) -> int:
        return self.frame.depth

    @property
    def invocation_name(self) -> str:
        return self.frame.invocation_name

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
        """Construct a RunContext for direct tool invocation.

        RunContext.prompt is derived from WorkerArgs for logging/UI only.
        Tools should use their args, not prompt text.

        String models are resolved to concrete Model instances via infer_model.
        """
        model: Model = (
            infer_model(resolved_model) if isinstance(resolved_model, str) else resolved_model
        )
        return RunContext(
            deps=deps_ctx,
            model=model,
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
        from .worker import WorkerToolset

        validator = tool.args_validator
        if isinstance(args, (str, bytes, bytearray)):
            json_input = args if args else "{}"
            validated = validator.validate_json(
                json_input,
                allow_partial="off",
                context=run_ctx.validation_context,
            )
            if isinstance(toolset, WorkerToolset):
                return ensure_worker_args(toolset.worker.schema_in, validated)
            return validated

        if args is None:
            args = {}
        validated = validator.validate_python(
            args,
            allow_partial="off",
            context=run_ctx.validation_context,
        )
        if isinstance(toolset, WorkerToolset):
            return ensure_worker_args(toolset.worker.schema_in, validated)
        return validated

    def spawn_child(
        self,
        active_toolsets: Optional[list[AbstractToolset[Any]]] = None,
        *,
        model: ModelType | None = None,
        invocation_name: str | None = None,
    ) -> "WorkerRuntime":
        """Spawn a child worker runtime with a forked CallFrame (depth+1)."""
        return WorkerRuntime(
            runtime=self.runtime,
            frame=self.frame.fork(
                active_toolsets,
                model=model,
                invocation_name=invocation_name,
            ),
        )

    async def call(self, name: str, input_data: Any) -> Any:
        """Call a tool by name (searched across toolsets).

        This enables programmatic tool invocation from code entry points:
            result = await ctx.deps.call("pitch_evaluator", {"input": "..."})

        Soft policy: tools should use their args, and only use ctx.deps
        for worker/tool delegation. Tool calls follow the runtime approval
        policy (entry functions stay in the tool plane).
        """
        import uuid

        from ..ui.events import ToolCallEvent, ToolResultEvent

        # Create a temporary run context for get_tools
        run_ctx = self._make_run_context(name, self.model, self)

        # Search for the tool across all toolsets
        for toolset in self.active_toolsets:
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

                worker_name = self.invocation_name or "unknown"

                # Emit ToolCallEvent before execution
                if self.on_event is not None:
                    self.on_event(
                        ToolCallEvent(
                            worker=worker_name,
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
                            worker=worker_name,
                            depth=self.depth,
                            tool_name=name,
                            tool_call_id=call_id,
                            content=result,
                        )
                    )

                return result

        available: list[str] = []
        for toolset in self.active_toolsets:
            tools = await toolset.get_tools(run_ctx)
            available.extend(tools.keys())
        raise KeyError(f"Tool '{name}' not found. Available: {available}")

    async def _execute(self, worker: "Worker", input_data: WorkerArgs) -> Any:
        """Execute a worker using this runtime as deps."""
        run_ctx = self._make_run_context(worker.name, self.model, self)
        return await worker.call(input_data, run_ctx)
