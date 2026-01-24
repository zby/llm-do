"""Runtime deps facade for tool execution."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from pydantic_ai.models import Model, infer_model
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from .call import CallFrame
from .contracts import CallRuntimeProtocol, ModelType
from .shared import Runtime, RuntimeConfig


class CallRuntime:
    """Dispatches tool calls and manages entry runtime state.

    CallRuntime is the central deps surface for executing tools and entries.
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

    @property
    def config(self) -> RuntimeConfig:
        return self.runtime.config

    def log_messages(self, worker_name: str, depth: int, messages: list[Any]) -> None:
        """Record messages for diagnostic logging."""
        self.runtime.log_messages(worker_name, depth, messages)

    def _create_usage(self) -> RunUsage:
        """Create a new RunUsage and add it to the shared usage sink."""
        return self.runtime._create_usage()

    def _make_run_context(self, tool_name: str) -> RunContext[CallRuntimeProtocol]:
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
        run_ctx: RunContext[CallRuntimeProtocol],
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
    ) -> "CallRuntime":
        """Spawn a child call runtime with a forked CallFrame (depth+1)."""
        if self.frame.config.depth >= self.config.max_depth:
            raise RuntimeError(
                f"Max depth exceeded calling '{invocation_name}': "
                f"depth {self.frame.config.depth} >= max {self.config.max_depth}"
            )
        return CallRuntime(
            runtime=self.runtime,
            frame=self.frame.fork(
                active_toolsets,
                model=model,
                invocation_name=invocation_name,
            ),
        )
