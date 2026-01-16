"""Runtime deps facade for tool execution."""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic_ai.models import Model, infer_model
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from .args import WorkerArgs
from .call import CallFrame
from .contracts import ModelType, WorkerRuntimeProtocol
from .events import ToolCallEvent, ToolResultEvent

if TYPE_CHECKING:
    from .worker import Worker

from .shared import Runtime, RuntimeConfig


class WorkerRuntime:
    """Dispatches tool calls and manages worker runtime state.

    WorkerRuntime is the central orchestrator for executing tools and workers.
    It holds:
    - runtime (Runtime): shared config and runtime-scoped state
    - frame (CallFrame): per-branch state (depth, prompt/messages, toolsets, model)

    Access runtime settings via config.*, call state via frame.*.
    """

    def __init__(
        self,
        *,
        runtime: Runtime,
        frame: CallFrame,
    ) -> None:
        self.runtime = runtime
        self.frame = frame

    @property
    def config(self) -> RuntimeConfig:
        return self.runtime.config

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(worker_name, depth, messages)

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self.runtime._create_usage()

    def _make_run_context(self, tool_name: str) -> RunContext[WorkerRuntimeProtocol]:
        """Construct a RunContext for direct tool invocation.

        RunContext.prompt is derived from WorkerArgs for logging/UI only.
        Tools should use their args, not prompt text.

        String models are resolved to concrete Model instances via infer_model.
        """
        model: Model = (
            infer_model(self.frame.model)
            if isinstance(self.frame.model, str)
            else self.frame.model
        )
        return RunContext(
            deps=self,
            model=model,
            usage=self._create_usage(),
            prompt=self.frame.prompt,
            messages=list(self.frame.messages),
            run_step=self.frame.depth,
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
        validator = tool.args_validator
        if isinstance(args, (str, bytes, bytearray)):
            json_input = args if args else "{}"
            validated = validator.validate_json(
                json_input,
                allow_partial="off",
                context=run_ctx.validation_context,
            )
            return validated

        if args is None:
            args = {}
        validated = validator.validate_python(
            args,
            allow_partial="off",
            context=run_ctx.validation_context,
        )
        return validated

    def spawn_child(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
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

        # Create a temporary run context for get_tools
        run_ctx = self._make_run_context(name)

        # Search for the tool across all toolsets, collecting names for error message
        available: list[str] = []
        for toolset in self.frame.active_toolsets:
            tools = await toolset.get_tools(run_ctx)
            available.extend(tools.keys())
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

                worker_name = self.frame.invocation_name or "unknown"

                # Emit ToolCallEvent before execution
                if self.config.on_event is not None:
                    self.config.on_event(
                        ToolCallEvent(
                            worker=worker_name,
                            tool_name=name,
                            tool_call_id=call_id,
                            args=validated_args,
                            depth=self.frame.depth,
                        )
                    )

                # Execute the tool
                result = await toolset.call_tool(name, validated_args, run_ctx, tool)

                # Emit ToolResultEvent after execution
                if self.config.on_event is not None:
                    self.config.on_event(
                        ToolResultEvent(
                            worker=worker_name,
                            depth=self.frame.depth,
                            tool_name=name,
                            tool_call_id=call_id,
                            content=result,
                        )
                    )

                return result

        raise KeyError(f"Tool '{name}' not found. Available: {available}")

    async def _execute(self, worker: "Worker", input_data: WorkerArgs) -> Any:
        """Execute a worker using this runtime as deps."""
        run_ctx = self._make_run_context(worker.name)
        return await worker.call(input_data, run_ctx)
