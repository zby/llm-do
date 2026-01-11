"""Invocable implementations for the context runtime.

This module provides:
- Worker: An LLM-powered worker that IS an AbstractToolset
- WorkerToolset: Adapter that exposes a Worker as a single tool for another agent
- ToolInvocable: Wrapper for tool-as-entrypoint usage
"""
from __future__ import annotations

import inspect
import json
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterable, Callable, Literal, Optional, Sequence, Type, cast

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
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai_blocking_approval import ApprovalDecision

from ..models import select_model
from ..toolsets.approval import get_toolset_approval_config, set_toolset_approval_config
from ..toolsets.attachments import AttachmentToolset
from ..ui.events import TextResponseEvent, ToolCallEvent, ToolResultEvent
from .approval import ApprovalCallback
from .args import WorkerArgs, WorkerInput, ensure_worker_args
from .call import CallFrame
from .contracts import WorkerRuntimeProtocol
from .shared import RuntimeConfig


def _resolve_attachment_path(path: str, base_path: Path | None = None) -> Path:
    """Resolve an attachment path to an absolute, normalized path.

    Args:
        path: Path to the file (relative or absolute)
        base_path: Base directory for resolving relative paths

    Returns:
        Absolute, normalized Path for the attachment
    """
    file_path = Path(path).expanduser()
    if not file_path.is_absolute() and base_path is not None:
        file_path = base_path.expanduser() / file_path
    return file_path.resolve()


def _build_user_prompt(
    text: str, attachments: Sequence[BinaryContent]
) -> str | Sequence[UserContent]:
    """Build a user prompt from text and resolved attachments."""
    # If no attachments, return plain string (avoid empty/whitespace prompt for providers that require a message)
    if not attachments:
        return text if text.strip() else "(no input)"

    # Build multimodal prompt with attachments
    parts: list[UserContent] = [text if text.strip() else "(no input)"]
    parts.extend(attachments)

    return parts


def _should_use_message_history(runtime: WorkerRuntimeProtocol) -> bool:
    """Only use message history for the top-level worker run."""
    return runtime.depth <= 1


def _get_all_messages(result: Any) -> list[Any]:
    """Return all messages from a run result or stream object.

    PydanticAI exposes all_messages() as a method (not a property) on both
    RunResult and StreamedRunResult with the same signature.
    See: https://ai.pydantic.dev/api/result/
    """
    return list(result.all_messages())


def _finalize_messages(
    worker_name: str,
    runtime: WorkerRuntimeProtocol,
    state: CallFrame | None,
    result: Any,
    *,
    log_messages: bool = True,
) -> list[Any]:
    """Log and sync message history using a single message snapshot."""
    messages = _get_all_messages(result)
    if log_messages:
        runtime.log_messages(worker_name, runtime.depth, messages)
    if _should_use_message_history(runtime):
        runtime.messages[:] = messages
        if state is not None:
            state.messages[:] = messages
    return messages


def _scoped_approval_callback(approval_callback: ApprovalCallback) -> ApprovalCallback:
    """Return a callback that bulk-approves after the first approval."""
    cached: ApprovalDecision | None = None

    async def callback(request) -> ApprovalDecision:
        nonlocal cached
        if cached is not None and cached.approved:
            return cached
        decision = approval_callback(request)
        if inspect.isawaitable(decision):
            decision = await decision
        if not isinstance(decision, ApprovalDecision):
            raise TypeError("approval_callback must return ApprovalDecision")
        if decision.approved:
            cached = decision
        return decision

    return callback


class _MessageLogList(list):
    """List that logs new messages as they are appended."""

    def __init__(self, runtime: WorkerRuntimeProtocol, worker_name: str, depth: int) -> None:
        super().__init__()
        self._runtime = runtime
        self._worker_name = worker_name
        self._depth = depth
        self._logged_count = 0

    def _log_new_messages(self, start: int) -> None:
        for message in list(self)[start:]:
            self._runtime.log_messages(self._worker_name, self._depth, [message])
        self._logged_count = len(self)

    def append(self, item: Any) -> None:  # type: ignore[override]
        super().append(item)
        self._log_new_messages(self._logged_count)

    def extend(self, items: list[Any]) -> None:  # type: ignore[override]
        start = len(self)
        super().extend(items)
        if len(self) > start:
            self._log_new_messages(start)


@contextmanager
def _capture_message_log(
    runtime: WorkerRuntimeProtocol, *, worker_name: str, depth: int
) -> Any:
    """Capture and log messages as they are appended for this run."""
    from pydantic_ai._agent_graph import capture_run_messages, get_captured_run_messages

    with capture_run_messages():
        try:
            run_messages = get_captured_run_messages()
        except LookupError:
            yield
            return
        run_messages.messages = _MessageLogList(runtime, worker_name, depth)
        yield


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


def build_worker_tool(
    worker: "Worker",
    toolset: AbstractToolset[Any],
) -> ToolsetTool[Any]:
    """Build a ToolsetTool for exposing a Worker as a callable tool.

    This shared helper is used by both Worker.get_tools() and WorkerToolset.get_tools()
    to ensure consistent tool definition and validation.

    Args:
        worker: The worker to expose as a tool
        toolset: The toolset that owns this tool (Worker or WorkerToolset)

    Returns:
        ToolsetTool configured for the worker
    """
    description_source = worker.description or worker.instructions
    description = (
        description_source[:200] + "..."
        if len(description_source) > 200
        else description_source
    )
    input_schema = worker.schema_in or WorkerInput

    tool_def = ToolDefinition(
        name=worker.name,
        description=description,
        parameters_json_schema=input_schema.model_json_schema(),
    )

    return ToolsetTool(
        toolset=toolset,
        tool_def=tool_def,
        max_retries=0,
        args_validator=_DictValidator(input_schema),
    )


@dataclass
class WorkerToolset(AbstractToolset[Any]):
    """Adapter that exposes a Worker as a single tool for another agent.

    This decouples "Worker as callable entry" from "Worker as tool provider",
    making the relationship explicit via composition rather than inheritance.

    The tool name is always worker.name (no attribute-name aliasing).

    Usage:
        analyst = Worker(name="analyst", ...)
        main_worker = Worker(
            name="main",
            toolsets=[analyst.as_toolset(), filesystem, shell],
            ...
        )
    """

    worker: "Worker"
    bulk_approve: bool = False

    def __post_init__(self) -> None:
        # Set up approval config for this toolset adapter
        config = get_toolset_approval_config(self)
        if config is None:
            set_toolset_approval_config(self, {self.worker.name: {"pre_approved": True}})

    @property
    def id(self) -> str | None:
        """Return the worker name as this toolset's id."""
        return self.worker.name

    async def get_tools(self, run_ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        """Return the wrapped worker as a callable tool."""
        tool = build_worker_tool(self.worker, self)
        return {self.worker.name: tool}

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        run_ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        """Execute the worker when called as a tool."""
        return await self.worker._call_internal(
            tool_args,
            run_ctx.deps.config,
            run_ctx.deps.frame,
            run_ctx,
        )


@dataclass
class ToolInvocable:
    """Wrapper for using a tool from a toolset as an entry point.

    This is used for the code entry pattern where a Python tool function
    is the main entry point instead of a worker.

    DEPRECATED: Use @entry decorator instead. This class will be removed
    in a future version.
    """

    toolset: AbstractToolset[Any]
    tool_name: str

    @property
    def name(self) -> str:
        return self.tool_name

    @property
    def toolsets(self) -> list[AbstractToolset[Any]]:
        """Return the toolset as a single-item list for Entry protocol compliance."""
        return [self.toolset]

    async def call(
        self,
        input_data: Any,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any:
        """Call the tool via its toolset.

        Args:
            input_data: Tool input (dict or BaseModel)
            run_ctx: PydanticAI RunContext for tool execution
        """
        if isinstance(input_data, BaseModel):
            input_data = input_data.model_dump()
        elif not isinstance(input_data, dict):
            raise TypeError(f"Expected dict or BaseModel, got {type(input_data)}")

        tools = await self.toolset.get_tools(run_ctx)
        tool = tools.get(self.tool_name)
        if tool is None:
            raise KeyError(f"Tool {self.tool_name} not found in toolset")

        return await self.toolset.call_tool(self.tool_name, input_data, run_ctx, tool)


# Type alias for toolset references: can be names (str) or instances
ToolsetRef = str | AbstractToolset[Any]


@dataclass
class EntryFunction:
    """Wrapper that implements the Entry protocol for decorated functions.

    Created by the @entry decorator to expose Python functions as entry points.
    Toolset references can be names (resolved during registry linking) or instances.

    Attributes:
        func: The wrapped async function
        entry_name: Name for this entry (from decorator or function name)
        toolset_refs: List of toolset references (names or instances)
        _resolved_toolsets: Resolved toolset instances (set during linking)
    """

    func: Callable[..., Any]
    entry_name: str
    toolset_refs: list[ToolsetRef] = field(default_factory=list)
    _resolved_toolsets: list[AbstractToolset[Any]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.entry_name

    @property
    def toolsets(self) -> list[AbstractToolset[Any]]:
        """Return resolved toolsets for Entry protocol.

        Note: If called before linking, only instance refs are available.
        Named refs require registry linking to resolve.
        """
        if self._resolved_toolsets:
            return self._resolved_toolsets
        # Fallback: return only instance refs (unlinked state)
        return [ref for ref in self.toolset_refs if isinstance(ref, AbstractToolset)]

    def resolve_toolsets(self, available: dict[str, AbstractToolset[Any]]) -> None:
        """Resolve named toolset refs to instances during registry linking.

        Args:
            available: Map of toolset names to instances from the registry
        """
        resolved: list[AbstractToolset[Any]] = []
        for ref in self.toolset_refs:
            if isinstance(ref, str):
                if ref not in available:
                    raise ValueError(
                        f"Entry '{self.name}' references unknown toolset: {ref}. "
                        f"Available: {sorted(available.keys())}"
                    )
                resolved.append(available[ref])
            else:
                resolved.append(ref)
        self._resolved_toolsets = resolved

    async def call(
        self,
        input_data: Any,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any:
        """Execute the wrapped function.

        Args:
            input_data: Entry input (typically dict with "input" key)
            run_ctx: PydanticAI RunContext for execution context
        """
        # Support both dict and direct input styles
        if isinstance(input_data, dict) and "input" in input_data:
            prompt = input_data["input"]
        elif isinstance(input_data, BaseModel):
            prompt = input_data.model_dump()
        else:
            prompt = input_data

        # Call the function with deps context
        result = self.func(prompt, run_ctx.deps)
        if inspect.isawaitable(result):
            result = await result
        return result


def entry(
    name: str | None = None,
    *,
    toolsets: list[ToolsetRef] | None = None,
) -> Callable[[Callable[..., Any]], EntryFunction]:
    """Decorator to mark a function as an entry point.

    The decorated function should accept (input, deps) where:
    - input: The prompt/input data (typically a string or dict)
    - deps: WorkerRuntime instance for accessing tools and context

    Args:
        name: Entry name (defaults to function name)
        toolsets: List of toolset references (names or instances)

    Returns:
        Decorator that wraps the function in an EntryFunction

    Example:
        @entry(name="analyzer", toolsets=["filesystem", "shell"])
        async def analyze(input: str, deps: WorkerRuntime) -> str:
            # Use deps.tools.shell(...) to call tools
            return f"Analyzed: {input}"
    """
    def decorator(func: Callable[..., Any]) -> EntryFunction:
        entry_name = name if name is not None else func.__name__
        return EntryFunction(
            func=func,
            entry_name=entry_name,
            toolset_refs=list(toolsets) if toolsets else [],
        )
    return decorator


@dataclass
class Worker:
    """An LLM-powered worker that can be run as an entry point.

    Worker represents an agent that uses an LLM to process prompts and can
    call tools to accomplish tasks. To expose a Worker as a tool for another
    agent, use the as_toolset() method to get a WorkerToolset adapter.

    Tools are passed as a list of AbstractToolsets which are combined
    and passed directly to the PydanticAI Agent.
    """

    name: str
    instructions: str
    description: str | None = None
    model: str | Model | None = None  # String identifier or Model object
    compatible_models: list[str] | None = None
    toolsets: list[AbstractToolset[Any]] = field(default_factory=list)
    builtin_tools: list[Any] = field(default_factory=list)  # PydanticAI builtin tools
    model_settings: Optional[ModelSettings] = None
    schema_in: Optional[Type[WorkerArgs]] = None
    schema_out: Optional[Type[BaseModel]] = None
    base_path: Optional[Path] = None  # Base directory for resolving relative attachment paths
    bulk_approve_toolsets: bool = False

    def __post_init__(self) -> None:
        if self.schema_in is not None and not issubclass(self.schema_in, WorkerArgs):
            raise TypeError(f"schema_in must subclass WorkerArgs; got {self.schema_in}")

    def as_toolset(self, *, bulk_approve: bool | None = None) -> WorkerToolset:
        """Return a WorkerToolset adapter for this worker.

        Use this method to explicitly expose a worker as a tool for another agent.

        Args:
            bulk_approve: If True, auto-approve subsequent calls after first approval.
                         Defaults to worker's bulk_approve_toolsets setting.

        Returns:
            WorkerToolset adapter wrapping this worker
        """
        if bulk_approve is None:
            bulk_approve = self.bulk_approve_toolsets
        return WorkerToolset(worker=self, bulk_approve=bulk_approve)

    def _build_agent(
        self,
        resolved_model: str | Model,
        runtime: WorkerRuntimeProtocol,
        *,
        toolsets: list[AbstractToolset[Any]] | None = None,
    ) -> Agent[WorkerRuntimeProtocol, Any]:
        """Build a PydanticAI agent with toolsets passed directly."""
        agent_toolsets = toolsets if toolsets is not None else self.toolsets
        return Agent(
            model=resolved_model,
            instructions=self.instructions,
            output_type=self.schema_out or str,
            deps_type=type(runtime),
            toolsets=agent_toolsets if agent_toolsets else None,
            builtin_tools=self.builtin_tools,  # Pass list (empty list is fine)
            # Use 'exhaustive' to ensure tool calls are executed even when
            # text output is present in the same response
            end_strategy="exhaustive",
        )

    def _emit_tool_events(
        self, messages: list[Any], runtime: WorkerRuntimeProtocol
    ) -> None:
        """Emit ToolCallEvent/ToolResultEvent for tool calls in messages."""
        if runtime.on_event is None:
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

            runtime.on_event(ToolCallEvent(
                worker=self.name,
                tool_name=call_part.tool_name,
                tool_call_id=call_id,
                args=args,
                depth=runtime.depth,
            ))

            return_part = tool_returns.get(call_id)
            if return_part:
                runtime.on_event(ToolResultEvent(
                    worker=self.name,
                    depth=runtime.depth,
                    tool_name=call_part.tool_name,
                    tool_call_id=call_id,
                    content=return_part.content,
                ))

    async def call(
        self,
        input_data: Any,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any:
        """Execute the worker with the given input.

        Args:
            input_data: Worker input args (WorkerArgs or dict)
            run_ctx: PydanticAI RunContext (deps is the parent WorkerRuntime)
        """
        return await self._call_internal(
            input_data,
            run_ctx.deps.config,
            run_ctx.deps.frame,
            run_ctx,
        )

    async def _call_internal(
        self,
        input_data: Any,
        config: RuntimeConfig,
        state: CallFrame,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any:
        """Shared worker execution path."""
        from .approval import wrap_toolsets_for_approval

        input_args = ensure_worker_args(self.schema_in, input_data)
        prompt_spec = input_args.prompt_spec()

        # Check depth limit using global config and per-call state
        if state.depth >= config.max_depth:
            raise RuntimeError(f"Max depth exceeded: {config.max_depth}")

        # Resolve model: worker model > state model (inherited from parent)
        resolved_model = select_model(
            worker_model=self.model,
            cli_model=state.model,
            compatible_models=self.compatible_models,
            worker_name=self.name,
        )

        # Wrap toolsets for approval using runtime-scoped callback
        approval_callback = run_ctx.deps.approval_callback
        if self.bulk_approve_toolsets:
            approval_callback = _scoped_approval_callback(approval_callback)
        wrapped_toolsets = wrap_toolsets_for_approval(
            self.toolsets or [],
            approval_callback,
            return_permission_errors=run_ctx.deps.return_permission_errors,
        )

        attachment_parts: list[BinaryContent] = []
        if prompt_spec.attachments:
            attachment_toolsets = wrap_toolsets_for_approval(
                [AttachmentToolset()],
                run_ctx.deps.approval_callback,
                return_permission_errors=False,
            )
            attachment_runtime = cast(
                Any,
                run_ctx.deps.spawn_child(
                    toolsets=attachment_toolsets,
                    model=resolved_model,
                ),
            )
            attachment_runtime.prompt = prompt_spec.text
            for attachment_path in prompt_spec.attachments:
                resolved_path = _resolve_attachment_path(attachment_path, self.base_path)
                attachment = await attachment_runtime.call(
                    "read_attachment",
                    {"path": str(resolved_path)},
                )
                if not isinstance(attachment, BinaryContent):
                    raise TypeError("Attachment tool must return BinaryContent")
                attachment_parts.append(attachment)

        # Fork per-call state and build child runtime for PydanticAI deps
        child_runtime = run_ctx.deps.spawn_child(toolsets=wrapped_toolsets, model=resolved_model)
        child_runtime.prompt = prompt_spec.text
        child_state = child_runtime.frame

        agent = self._build_agent(resolved_model, child_runtime, toolsets=wrapped_toolsets)
        prompt = _build_user_prompt(prompt_spec.text, attachment_parts)
        message_history = (
            list(state.messages) if _should_use_message_history(child_runtime) and state.messages else None
        )

        use_incremental_log = config.message_log_callback is not None
        log_context = (
            _capture_message_log(child_runtime, worker_name=self.name, depth=child_state.depth)
            if use_incremental_log
            else nullcontext()
        )

        with log_context:
            if config.on_event is not None:
                if config.verbosity >= 2:
                    output = await self._run_streaming(
                        agent,
                        prompt,
                        child_runtime,
                        message_history,
                        log_messages=not use_incremental_log,
                    )
                else:
                    output = await self._run_with_event_stream(
                        agent,
                        prompt,
                        child_runtime,
                        message_history,
                        log_messages=not use_incremental_log,
                    )
                if _should_use_message_history(child_runtime):
                    state.messages[:] = list(child_state.messages)
            else:
                result = await agent.run(
                    prompt,
                    deps=child_runtime,
                    model_settings=self.model_settings,
                    message_history=message_history,
                )
                _finalize_messages(
                    self.name,
                    child_runtime,
                    state,
                    result,
                    log_messages=not use_incremental_log,
                )
                output = result.output

        return output

    async def _run_with_event_stream(
        self,
        agent: Agent[WorkerRuntimeProtocol, Any],
        prompt: str | Sequence[UserContent],
        runtime: WorkerRuntimeProtocol,
        message_history: list[Any] | None,
        *,
        log_messages: bool = True,
    ) -> Any:
        """Run agent with event stream handler for non-streaming UI updates."""
        from pydantic_ai.messages import PartDeltaEvent

        from ..ui.parser import parse_event

        emitted_tool_events = False

        async def event_stream_handler(
            _: RunContext[WorkerRuntimeProtocol],
            events: AsyncIterable[Any],
        ) -> None:
            nonlocal emitted_tool_events
            async for event in events:
                if runtime.verbosity < 2 and isinstance(event, PartDeltaEvent):
                    continue
                ui_event = parse_event({"worker": self.name, "event": event, "depth": runtime.depth})
                if isinstance(ui_event, (ToolCallEvent, ToolResultEvent)):
                    emitted_tool_events = True
                if runtime.on_event is not None:
                    runtime.on_event(ui_event)

        result = await agent.run(
            prompt,
            deps=runtime,
            model_settings=self.model_settings,
            event_stream_handler=event_stream_handler,
            message_history=message_history,
        )
        _finalize_messages(
            self.name,
            runtime,
            None,
            result,
            log_messages=log_messages,
        )
        if runtime.on_event is not None and not emitted_tool_events:
            self._emit_tool_events(result.new_messages(), runtime)
        return result.output

    async def _run_streaming(
        self,
        agent: Agent[WorkerRuntimeProtocol, Any],
        prompt: str | Sequence[UserContent],
        runtime: WorkerRuntimeProtocol,
        message_history: list[Any] | None,
        *,
        log_messages: bool = True,
    ) -> Any:
        """Run agent with streaming, emitting text deltas."""
        async with agent.run_stream(
            prompt,
            deps=runtime,
            model_settings=self.model_settings,
            message_history=message_history,
        ) as stream:
            # Stream text deltas
            output: Any
            if self.schema_out is None or self.schema_out is str:
                async for chunk in stream.stream_text(delta=True):
                    if runtime.on_event:
                        runtime.on_event(TextResponseEvent(
                            worker=self.name,
                            depth=runtime.depth,
                            content=chunk,
                            is_delta=True,
                            is_complete=False,  # Not complete - this is a streaming delta
                        ))
                # Avoid double completion; validate without re-marking completed.
                output = await stream.validate_response_output(stream.response)
                if runtime.on_event and isinstance(output, str):
                    runtime.on_event(TextResponseEvent(
                        worker=self.name,
                        depth=runtime.depth,
                        content=output,
                        is_complete=True,
                        is_delta=False,
                    ))
            else:
                output = await stream.get_output()
                if runtime.on_event and isinstance(output, str):
                    runtime.on_event(TextResponseEvent(
                        worker=self.name,
                        depth=runtime.depth,
                        content=output,
                        is_complete=True,
                        is_delta=False,
                    ))

            _finalize_messages(
                self.name,
                runtime,
                None,
                stream,
                log_messages=log_messages,
            )
            # Emit tool events (must be inside context manager)
            self._emit_tool_events(stream.new_messages(), runtime)

        return output
