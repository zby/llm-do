"""Runtime deps facade for tool execution."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from pydantic_ai.models import Model, infer_model
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset
from pydantic_ai.usage import RunUsage

from ..models import NullModel
from ..toolsets.loader import ToolsetBuildContext, instantiate_toolsets
from .agent_runner import run_agent
from .approval import wrap_toolsets_for_approval
from .call import CallFrame, CallScope
from .contracts import AgentSpec, ModelType, WorkerRuntimeProtocol
from .events import ToolCallEvent, ToolResultEvent
from .shared import Runtime, RuntimeConfig


class WorkerRuntime:
    """Dispatches tool calls and agent runs, managing call-scoped state.

    WorkerRuntime is the central orchestrator for executing tools and agents.
    It holds:
    - runtime (Runtime): shared config and runtime-scoped state
    - frame (CallFrame): per-branch state (prompt/messages + immutable config)

    Access runtime settings via config.*, call state via frame.prompt/messages and frame.config.*.
    """

    def __init__(
        self,
        *,
        runtime: Runtime,
        frame: CallFrame,
    ) -> None:
        self.runtime = runtime
        self.frame = frame
        self._entry_history_consumed = False

    @property
    def config(self) -> RuntimeConfig:
        return self.runtime.config

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(worker_name, depth, messages)

    def reset_entry_history(self) -> None:
        """Allow a new entry turn to pass message history into call_agent."""
        self._entry_history_consumed = False

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
            infer_model(self.frame.config.model)
            if isinstance(self.frame.config.model, str)
            else self.frame.config.model
        )
        return RunContext(
            deps=self,
            model=model,
            usage=self._create_usage(),
            prompt=self.frame.prompt,
            messages=list(self.frame.messages),
            run_step=self.frame.config.depth,
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
        from .args import Attachment

        args = input_data
        if isinstance(args, BaseModel):
            args = args.model_dump()
        # Convert message list to dict format for tool schema validation
        elif isinstance(args, list):
            text_parts = []
            attachments = []
            for item in args:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, Attachment):
                    attachments.append(str(item.path))
            args = {"input": " ".join(text_parts)}
            if attachments:
                args["attachments"] = attachments
        validator = tool.args_validator
        if isinstance(args, (str, bytes, bytearray)):
            json_input = args if args else "{}"
            validated = validator.validate_json(
                json_input,
                allow_partial="off",
                context=run_ctx.validation_context,
            )
            if isinstance(validated, BaseModel):
                return validated.model_dump()
            return validated

        if args is None:
            args = {}
        validated = validator.validate_python(
            args,
            allow_partial="off",
            context=run_ctx.validation_context,
        )
        if isinstance(validated, BaseModel):
            return validated.model_dump()
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

    async def _call_tool(self, name: str, input_data: Any) -> Any:
        """Call a tool by name (searched across toolsets)."""
        import uuid

        # Create a temporary run context for get_tools
        run_ctx = self._make_run_context(name)

        combined_toolset = CombinedToolset(self.frame.config.active_toolsets)
        tools = await combined_toolset.get_tools(run_ctx)
        tool = tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found. Available: {list(tools.keys())}")

        validated_args = self._validate_tool_args(
            tool.toolset,
            tool,
            input_data,
            run_ctx,
        )

        # Generate a unique call ID for event correlation
        call_id = str(uuid.uuid4())[:8]

        worker_name = self.frame.config.invocation_name or "unknown"

        is_entry_call = (
            self.frame.config.depth == 0
            and name == "main"
            and isinstance(self.frame.config.model, NullModel)
        )

        # Emit ToolCallEvent before execution (skip entry tool invocation)
        if self.config.on_event is not None and not is_entry_call:
            self.config.on_event(
                ToolCallEvent(
                    worker=worker_name,
                    tool_name=name,
                    tool_call_id=call_id,
                    args=validated_args,
                    depth=self.frame.config.depth,
                )
            )

        # Execute the tool
        result = await combined_toolset.call_tool(name, validated_args, run_ctx, tool)

        # Emit ToolResultEvent after execution (skip entry tool invocation)
        if self.config.on_event is not None and not is_entry_call:
            self.config.on_event(
                ToolResultEvent(
                    worker=worker_name,
                    depth=self.frame.config.depth,
                    tool_name=name,
                    tool_call_id=call_id,
                    content=result,
                )
            )

        return result

    def _resolve_agent_spec(self, spec_or_name: AgentSpec | str) -> AgentSpec:
        if isinstance(spec_or_name, AgentSpec):
            return spec_or_name
        if not isinstance(spec_or_name, str):
            raise TypeError("call_agent expects AgentSpec or str")
        registry = self.runtime.agent_registry
        try:
            return registry[spec_or_name]
        except KeyError as exc:
            available = sorted(registry.keys())
            raise ValueError(
                f"Agent '{spec_or_name}' not found. Available: {available}"
            ) from exc

    async def call_agent(self, spec_or_name: AgentSpec | str, input_data: Any) -> Any:
        """Invoke a configured agent by spec or name (depth boundary)."""
        if self.frame.config.depth >= self.config.max_depth:
            raise RuntimeError("max_depth exceeded")

        spec = self._resolve_agent_spec(spec_or_name)

        toolset_context = spec.toolset_context or ToolsetBuildContext(
            worker_name=spec.name
        )
        toolsets = instantiate_toolsets(spec.toolset_specs, toolset_context)
        wrapped_toolsets = wrap_toolsets_for_approval(
            toolsets,
            self.config.approval_callback,
            return_permission_errors=self.config.return_permission_errors,
        )

        child_runtime = self.spawn_child(
            active_toolsets=wrapped_toolsets,
            model=spec.model,
            invocation_name=spec.name,
        )

        scope = CallScope(runtime=child_runtime, toolsets=toolsets)

        use_entry_history = (
            self.frame.config.depth == 0 and not self._entry_history_consumed
        )
        message_history = list(self.frame.messages) if use_entry_history else None

        try:
            output, messages = await run_agent(
                spec,
                child_runtime,
                input_data,
                message_history=message_history,
            )
        finally:
            await scope.close()

        if use_entry_history:
            self.frame.messages[:] = messages
            self._entry_history_consumed = True

        return output
