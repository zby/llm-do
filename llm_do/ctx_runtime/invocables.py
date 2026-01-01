"""Invocable implementations for the context runtime.

This module provides:
- WorkerInvocable: An LLM-powered worker that IS an AbstractToolset
- ToolInvocable: Wrapper for tool-as-entrypoint usage
"""
from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterable, Literal, Optional, Sequence, Type

from pydantic import BaseModel, TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.messages import (
    BinaryContent,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
)
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

if TYPE_CHECKING:
    from .ctx import ModelType, WorkerRuntime

from ..ui.events import TextResponseEvent, ToolCallEvent, ToolResultEvent


class WorkerInput(BaseModel):
    """Input schema for workers."""
    input: str
    attachments: list[str] = []


def _format_prompt(input_data: Any) -> str:
    """Format input data as a string prompt."""
    if isinstance(input_data, BaseModel):
        return input_data.model_dump_json(indent=2)
    if isinstance(input_data, dict):
        return json.dumps(input_data, indent=2)
    return str(input_data)


def _load_attachment(path: str) -> BinaryContent:
    """Load a file as BinaryContent for use in multimodal prompts.

    Args:
        path: Path to the file (relative or absolute)

    Returns:
        BinaryContent with file data and detected media type

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Attachment not found: {path}")

    # Detect media type from extension
    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        # Default to octet-stream for unknown types
        media_type = "application/octet-stream"

    data = file_path.read_bytes()
    return BinaryContent(data=data, media_type=media_type)


def _build_user_prompt(input_data: Any) -> str | Sequence[UserContent]:
    """Build user prompt from input data, handling attachments.

    If input_data contains attachments, returns a sequence of UserContent
    parts (text + binary content). Otherwise returns a plain string.

    Args:
        input_data: Dict with 'input' and optional 'attachments' keys,
                   or a plain string/BaseModel

    Returns:
        String prompt or sequence of UserContent parts
    """
    # Extract text and attachments
    attachments: list[str] = []

    if isinstance(input_data, dict):
        text = str(input_data.get("input", input_data))
        attachments = input_data.get("attachments", [])
    elif isinstance(input_data, BaseModel):
        text = getattr(input_data, "input", str(input_data))
        attachments = getattr(input_data, "attachments", [])
    else:
        text = str(input_data)

    # If no attachments, return plain string
    if not attachments:
        return text

    # Build multimodal prompt with attachments
    parts: list[UserContent] = [text]
    for attachment_path in attachments:
        parts.append(_load_attachment(attachment_path))

    return parts


def _should_use_message_history(ctx: "WorkerRuntime") -> bool:
    """Only use message history for the top-level worker run."""
    return ctx.depth <= 1


def _get_all_messages(result: Any) -> list[Any]:
    """Return all messages from a run result or stream object."""
    all_messages = getattr(result, "all_messages", None)
    if callable(all_messages):
        return list(all_messages())
    if all_messages is not None:
        return list(all_messages)
    return []


def _update_message_history(ctx: "WorkerRuntime", result: Any) -> None:
    """Update message history in-place to keep shared references intact."""
    ctx.messages[:] = _get_all_messages(result)


class _DictValidator:
    """Validator wrapper that validates against schema but returns dict.

    This is needed because ApprovalToolset expects tool_args to be a dict,
    but TypeAdapter.validator returns the validated BaseModel instance.

    Wraps a pydantic validator to provide the same interface (validate_python,
    validate_json, validate_strings) but converts BaseModel results to dicts.
    """

    def __init__(self, schema: Type[BaseModel]) -> None:
        self._adapter = TypeAdapter(schema)
        self._inner = self._adapter.validator

    def _to_dict(self, result: Any) -> dict[str, Any]:
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result

    def validate_python(
        self,
        input: Any,
        *,
        allow_partial: bool | Literal["off", "on", "trailing-strings"] = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = self._inner.validate_python(input, allow_partial=allow_partial, **kwargs)
        return self._to_dict(result)

    def validate_json(
        self,
        input: str | bytes | bytearray,
        *,
        allow_partial: bool | Literal["off", "on", "trailing-strings"] = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = self._inner.validate_json(input, allow_partial=allow_partial, **kwargs)
        return self._to_dict(result)

    def validate_strings(self, data: Any, **kwargs: Any) -> dict[str, Any]:
        result = self._inner.validate_strings(data, **kwargs)
        return self._to_dict(result)


@dataclass
class ToolInvocable:
    """Wrapper for using a tool from a toolset as an entry point.

    This is used for the code entry pattern where a Python tool function
    is the main entry point instead of a worker.
    """

    toolset: AbstractToolset[Any]
    tool_name: str
    kind: str = "tool"
    model: ModelType | None = None
    toolsets: list[AbstractToolset[Any]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.tool_name

    async def call(
        self,
        input_data: Any,
        ctx: "WorkerRuntime",
        run_ctx: RunContext["WorkerRuntime"],
    ) -> Any:
        """Call the tool via its toolset."""
        if isinstance(input_data, BaseModel):
            input_data = input_data.model_dump()
        elif not isinstance(input_data, dict):
            raise TypeError(f"Expected dict or BaseModel, got {type(input_data)}")

        tools = await self.toolset.get_tools(run_ctx)
        tool = tools.get(self.tool_name)
        if tool is None:
            raise KeyError(f"Tool {self.tool_name} not found in toolset")

        return await self.toolset.call_tool(self.tool_name, input_data, run_ctx, tool)


@dataclass
class WorkerInvocable(AbstractToolset[Any]):
    """An LLM-powered worker that is also an AbstractToolset.

    WorkerInvocable represents an agent that uses an LLM to process
    prompts and can call tools to accomplish tasks. As an AbstractToolset,
    it can be composed into other workers' toolsets.

    Tools are passed as a list of AbstractToolsets which are combined
    and passed directly to the PydanticAI Agent.
    """

    name: str
    instructions: str
    model: ModelType | None = None
    toolsets: list[AbstractToolset[Any]] = field(default_factory=list)
    builtin_tools: list[Any] = field(default_factory=list)  # PydanticAI builtin tools
    model_settings: Optional[ModelSettings] = None
    schema_in: Optional[Type[BaseModel]] = None
    schema_out: Optional[Type[BaseModel]] = None
    kind: str = "worker"

    # AbstractToolset implementation
    @property
    def id(self) -> str | None:
        """Return the worker name as its toolset id."""
        return self.name

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        """Return this worker as a callable tool."""
        description = self.instructions[:200] + "..." if len(self.instructions) > 200 else self.instructions
        input_schema = self.schema_in or WorkerInput

        tool_def = ToolDefinition(
            name=self.name,
            description=description,
            parameters_json_schema=input_schema.model_json_schema(),
        )

        return {self.name: ToolsetTool(
            toolset=self,
            tool_def=tool_def,
            max_retries=0,
            args_validator=_DictValidator(input_schema),
        )}

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[Any], tool: ToolsetTool[Any]
    ) -> Any:
        """Execute the worker when called as a tool."""
        return await self.call(tool_args, ctx.deps, ctx)

    def _build_agent(self, resolved_model: ModelType, ctx: "WorkerRuntime") -> Agent["WorkerRuntime", Any]:
        """Build a PydanticAI agent with toolsets passed directly."""
        return Agent(
            model=resolved_model,
            instructions=self.instructions,
            output_type=self.schema_out or str,
            deps_type=type(ctx),
            toolsets=self.toolsets if self.toolsets else None,
            builtin_tools=self.builtin_tools,  # Pass list (empty list is fine)
            # Use 'exhaustive' to ensure tool calls are executed even when
            # text output is present in the same response
            end_strategy="exhaustive",
        )

    def _emit_tool_events(self, messages: list[Any], ctx: "WorkerRuntime") -> None:
        """Emit ToolCallEvent/ToolResultEvent for tool calls in messages."""
        if ctx.on_event is None:
            return

        # Collect tool calls and their returns
        tool_calls: dict[str, ToolCallPart] = {}
        tool_returns: dict[str, ToolReturnPart] = {}

        for msg in messages:
            if isinstance(msg, ModelResponse):
                for response_part in msg.parts:
                    if isinstance(response_part, ToolCallPart):
                        tool_calls[response_part.tool_call_id] = response_part
            elif isinstance(msg, ModelRequest):
                for request_part in msg.parts:
                    if isinstance(request_part, ToolReturnPart):
                        tool_returns[request_part.tool_call_id] = request_part

        # Emit events for each tool call/result pair
        for call_id, call_part in tool_calls.items():
            # Parse args from JSON string if needed
            args = call_part.args
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            elif not isinstance(args, dict):
                args = {}

            ctx.on_event(ToolCallEvent(
                worker=self.name,
                tool_name=call_part.tool_name,
                tool_call_id=call_id,
                args=args,
            ))

            return_part = tool_returns.get(call_id)
            if return_part:
                ctx.on_event(ToolResultEvent(
                    worker=self.name,
                    tool_name=call_part.tool_name,
                    tool_call_id=call_id,
                    content=return_part.content,
                ))

    async def call(
        self,
        input_data: Any,
        ctx: "WorkerRuntime",
        run_ctx: RunContext["WorkerRuntime"],
    ) -> Any:
        """Execute the worker with the given input."""
        if self.schema_in is not None:
            input_data = self.schema_in.model_validate(input_data)

        if ctx.depth >= ctx.max_depth:
            raise RuntimeError(f"Max depth exceeded: {ctx.max_depth}")

        resolved_model = self.model if self.model is not None else ctx.model
        child_ctx = ctx.spawn_child(
            toolsets=self.toolsets,
            model=resolved_model,
        )

        agent = self._build_agent(resolved_model, child_ctx)
        prompt = _build_user_prompt(input_data)
        message_history = (
            list(ctx.messages) if _should_use_message_history(child_ctx) and ctx.messages else None
        )

        if child_ctx.on_event is not None:
            if child_ctx.verbosity >= 2:
                output = await self._run_streaming(agent, prompt, child_ctx, message_history)
            else:
                output = await self._run_with_event_stream(agent, prompt, child_ctx, message_history)
            if _should_use_message_history(child_ctx):
                ctx.messages[:] = list(child_ctx.messages)
        else:
            result = await agent.run(
                prompt,
                deps=child_ctx,
                model_settings=self.model_settings,
                message_history=message_history,
            )
            if _should_use_message_history(child_ctx):
                _update_message_history(child_ctx, result)
                _update_message_history(ctx, result)
            output = result.output

        return output

    async def _run_with_event_stream(
        self,
        agent: Agent["WorkerRuntime", Any],
        prompt: str | Sequence[UserContent],
        ctx: "WorkerRuntime",
        message_history: list[Any] | None,
    ) -> Any:
        """Run agent with event stream handler for non-streaming UI updates."""
        from pydantic_ai.messages import PartDeltaEvent

        from ..ui.parser import parse_event

        emitted_tool_events = False

        async def event_stream_handler(
            _: RunContext["WorkerRuntime"],
            events: AsyncIterable[Any],
        ) -> None:
            nonlocal emitted_tool_events
            async for event in events:
                if ctx.verbosity < 2 and isinstance(event, PartDeltaEvent):
                    continue
                ui_event = parse_event({"worker": self.name, "event": event})
                if isinstance(ui_event, (ToolCallEvent, ToolResultEvent)):
                    emitted_tool_events = True
                if ctx.on_event is not None:
                    ctx.on_event(ui_event)

        result = await agent.run(
            prompt,
            deps=ctx,
            model_settings=self.model_settings,
            event_stream_handler=event_stream_handler,
            message_history=message_history,
        )
        if ctx.on_event is not None and not emitted_tool_events:
            self._emit_tool_events(result.new_messages(), ctx)
        if _should_use_message_history(ctx):
            _update_message_history(ctx, result)
        return result.output

    async def _run_streaming(
        self,
        agent: Agent["WorkerRuntime", Any],
        prompt: str | Sequence[UserContent],
        ctx: "WorkerRuntime",
        message_history: list[Any] | None,
    ) -> Any:
        """Run agent with streaming, emitting text deltas."""
        async with agent.run_stream(
            prompt,
            deps=ctx,
            model_settings=self.model_settings,
            message_history=message_history,
        ) as stream:
            # Stream text deltas
            async for chunk in stream.stream_text(delta=True):
                if ctx.on_event:
                    ctx.on_event(TextResponseEvent(
                        worker=self.name,
                        content=chunk,
                        is_delta=True,
                        is_complete=False,  # Not complete - this is a streaming delta
                    ))

            # Get the final output
            output = await stream.get_output()

            if ctx.on_event:
                ctx.on_event(TextResponseEvent(
                    worker=self.name,
                    content=output,
                    is_complete=True,
                    is_delta=False,
                ))

            # Emit tool events (must be inside context manager)
            self._emit_tool_events(stream.new_messages(), ctx)
            if _should_use_message_history(ctx):
                _update_message_history(ctx, stream)

        return output
