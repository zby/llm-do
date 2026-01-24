"""Per-call scope for entries (config + mutable state)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from pydantic import BaseModel
from pydantic_ai.models import Model, infer_model
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset
from pydantic_ai.usage import RunUsage

from .args import Attachment
from .contracts import ModelType, WorkerRuntimeProtocol
from .events import ToolCallEvent, ToolResultEvent
from .toolsets import cleanup_toolsets


@dataclass(frozen=True, slots=True)
class CallConfig:
    """Immutable call configuration - set at fork time, never changed."""

    active_toolsets: tuple[AbstractToolset[Any], ...]
    model: ModelType
    depth: int = 0
    invocation_name: str = ""

    @classmethod
    def build(
        cls,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        depth: int,
        invocation_name: str,
    ) -> "CallConfig":
        """Normalize toolsets and construct a CallConfig."""
        return cls(
            active_toolsets=tuple(active_toolsets),
            model=model,
            depth=depth,
            invocation_name=invocation_name,
        )

    def fork(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallConfig":
        """Create a child config with incremented depth."""
        return self.build(
            active_toolsets,
            model=model,
            depth=self.depth + 1,
            invocation_name=invocation_name,
        )


@dataclass(slots=True)
class CallFrame:
    """Per-worker call state with immutable config and mutable conversation state."""

    config: CallConfig

    # Mutable fields (required for runtime behavior)
    prompt: str = ""
    messages: list[Any] = field(default_factory=list)

    def fork(
        self,
        active_toolsets: Sequence[AbstractToolset[Any]],
        *,
        model: ModelType,
        invocation_name: str,
    ) -> "CallFrame":
        """Create child frame with incremented depth and fresh messages."""
        new_config = self.config.fork(
            active_toolsets,
            model=model,
            invocation_name=invocation_name,
        )
        return CallFrame(config=new_config)


@dataclass(slots=True)
class CallScope:
    """Lifecycle wrapper for a call scope (runtime + toolsets)."""

    runtime: WorkerRuntimeProtocol
    toolsets: Sequence["AbstractToolset[Any]"]
    _closed: bool = False

    def _create_usage(self) -> RunUsage:
        runtime = cast(Any, self.runtime)
        shared_runtime = getattr(runtime, "runtime", None)
        if shared_runtime is not None:
            create_usage = getattr(shared_runtime, "_create_usage", None)
            if callable(create_usage):
                return create_usage()
        return RunUsage()

    def _make_run_context(self, tool_name: str) -> RunContext[WorkerRuntimeProtocol]:
        """Construct a RunContext for direct tool invocation."""
        model: Model = (
            infer_model(self.runtime.frame.config.model)
            if isinstance(self.runtime.frame.config.model, str)
            else self.runtime.frame.config.model
        )
        return RunContext(
            deps=self.runtime,
            model=model,
            usage=self._create_usage(),
            prompt=self.runtime.frame.prompt,
            messages=list(self.runtime.frame.messages),
            run_step=self.runtime.frame.config.depth,
            retry=0,
            tool_name=tool_name,
        )

    def _validate_tool_args(
        self,
        tool: Any,
        input_data: Any,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any:
        """Validate tool args for direct calls to match PydanticAI behavior."""
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

    async def call_tool(self, name: str, input_data: Any) -> Any:
        if self._closed:
            raise RuntimeError("CallScope is closed")
        import uuid

        run_ctx = self._make_run_context(name)
        combined_toolset = CombinedToolset(self.runtime.frame.config.active_toolsets)
        tools = await combined_toolset.get_tools(run_ctx)
        tool = tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found. Available: {list(tools.keys())}")

        validated_args = self._validate_tool_args(tool, input_data, run_ctx)

        call_id = str(uuid.uuid4())[:8]
        worker_name = self.runtime.frame.config.invocation_name or "unknown"

        if self.runtime.config.on_event is not None:
            self.runtime.config.on_event(
                ToolCallEvent(
                    worker=worker_name,
                    tool_name=name,
                    tool_call_id=call_id,
                    args=validated_args,
                    depth=self.runtime.frame.config.depth,
                )
            )

        result = await combined_toolset.call_tool(name, validated_args, run_ctx, tool)

        if self.runtime.config.on_event is not None:
            self.runtime.config.on_event(
                ToolResultEvent(
                    worker=worker_name,
                    depth=self.runtime.frame.config.depth,
                    tool_name=name,
                    tool_call_id=call_id,
                    content=result,
                )
            )

        return result

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await cleanup_toolsets(self.toolsets)

    async def __aenter__(self) -> "CallScope":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
