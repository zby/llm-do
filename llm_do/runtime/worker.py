"""Entry implementations: Worker, WorkerToolset, EntryFunction."""
from __future__ import annotations

import inspect
import mimetypes
from contextlib import contextmanager, nullcontext
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterable, Callable, Optional, Sequence, Type

from pydantic import BaseModel
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
from pydantic_ai_blocking_approval import ApprovalResult

from ..models import select_model
from ..toolsets.approval import set_toolset_approval_config
from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec
from ..toolsets.validators import DictValidator
from .args import PromptSpec, WorkerArgs, WorkerInput, ensure_worker_args
from .call import CallFrame
from .contracts import WorkerRuntimeProtocol
from .events import ToolCallEvent, ToolResultEvent
from .shared import RuntimeConfig, build_tool_plane


def _resolve_attachment_path(path: str, base_path: Path | None = None) -> Path:
    """Resolve an attachment path to an absolute, normalized path."""
    file_path = Path(path).expanduser()
    if not file_path.is_absolute() and base_path is not None:
        file_path = base_path.expanduser() / file_path
    return file_path.resolve()


def _load_attachment(path: Path) -> BinaryContent:
    """Read attachment data from disk and infer media type."""
    if not path.exists():
        raise FileNotFoundError(f"Attachment not found: {path}")

    media_type, _ = mimetypes.guess_type(str(path))
    if media_type is None:
        media_type = "application/octet-stream"

    data = path.read_bytes()
    return BinaryContent(data=data, media_type=media_type)


def _build_user_prompt(text: str, attachments: Sequence[BinaryContent]) -> str | Sequence[UserContent]:
    """Build a user prompt from text and resolved attachments."""
    if not attachments:
        return text if text.strip() else "(no input)"
    parts: list[UserContent] = [text if text.strip() else "(no input)"]
    parts.extend(attachments)
    return parts


def _should_use_message_history(runtime: WorkerRuntimeProtocol) -> bool:
    """Only use message history for the top-level worker run."""
    return runtime.frame.depth <= 1


def _get_all_messages(result: Any) -> list[Any]:
    """Return all messages from a run result or stream object."""
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
        runtime.log_messages(worker_name, runtime.frame.depth, messages)
    if _should_use_message_history(runtime):
        runtime.frame.messages[:] = messages
        if state is not None:
            state.messages[:] = messages
    return messages


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


def build_worker_tool(worker: "Worker", toolset: AbstractToolset[Any]) -> ToolsetTool[Any]:
    """Build a ToolsetTool for exposing a Worker as a callable tool."""
    desc = worker.description or worker.instructions
    desc = desc[:200] + "..." if len(desc) > 200 else desc
    schema = worker.schema_in or WorkerInput
    return ToolsetTool(
        toolset=toolset,
        tool_def=ToolDefinition(name=worker.name, description=desc, parameters_json_schema=schema.model_json_schema()),
        max_retries=0,
        args_validator=DictValidator(schema),
    )


@dataclass
class WorkerToolset(AbstractToolset[Any]):
    """Adapter that exposes a Worker as a single tool for another agent."""
    worker: "Worker"

    @property
    def id(self) -> str | None:
        return self.worker.name

    def _prompt_spec_from_args(
        self, tool_args: dict[str, Any]
    ) -> PromptSpec | None:
        try:
            args = ensure_worker_args(self.worker.schema_in, tool_args)
        except Exception:
            return None
        return args.prompt_spec()

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: dict[str, dict[str, Any]] | None = None,
    ) -> ApprovalResult:
        tool_config = (config or {}).get(name)
        if tool_config is not None and "pre_approved" in tool_config:
            if tool_config["pre_approved"]:
                return ApprovalResult.pre_approved()
            return ApprovalResult.needs_approval()

        runtime_config = getattr(getattr(ctx, "deps", None), "config", None)
        require_all = getattr(runtime_config, "worker_calls_require_approval", False)
        require_attachments = getattr(
            runtime_config, "worker_attachments_require_approval", False
        )
        overrides = getattr(runtime_config, "worker_approval_overrides", {}) or {}
        override = overrides.get(name)
        if override is not None:
            if override.calls_require_approval is not None:
                require_all = override.calls_require_approval
            if override.attachments_require_approval is not None:
                require_attachments = override.attachments_require_approval
        if require_all:
            return ApprovalResult.needs_approval()

        prompt_spec = self._prompt_spec_from_args(tool_args)
        attachments = (
            prompt_spec.attachments
            if prompt_spec is not None
            else tuple(tool_args.get("attachments") or ())
        )
        if attachments and require_attachments:
            return ApprovalResult.needs_approval()
        return ApprovalResult.pre_approved()

    def get_approval_description(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
    ) -> str:
        prompt_spec = self._prompt_spec_from_args(tool_args)
        attachments = (
            prompt_spec.attachments
            if prompt_spec is not None
            else tuple(tool_args.get("attachments") or ())
        )
        if attachments:
            attachment_list = ", ".join(str(path) for path in attachments)
            return f"Call worker {name} with attachments: {attachment_list}"
        return f"Call worker {name}"

    async def get_tools(self, run_ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        return {self.worker.name: build_worker_tool(self.worker, self)}

    async def call_tool(self, name: str, tool_args: dict[str, Any], run_ctx: RunContext[Any], tool: ToolsetTool[Any]) -> Any:
        return await self.worker._call_internal(tool_args, run_ctx.deps.config, run_ctx.deps.frame, run_ctx)


ToolsetRef = str | ToolsetSpec


@dataclass
class EntryFunction:
    """Wrapper that implements the Entry protocol for decorated functions."""
    func: Callable[..., Any]
    entry_name: str
    toolset_refs: list[ToolsetRef] = field(default_factory=list)
    schema_in: Optional[Type[WorkerArgs]] = None
    toolset_context: ToolsetBuildContext | None = None
    _resolved_toolset_specs: list[ToolsetSpec] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.entry_name

    @property
    def toolset_specs(self) -> list[ToolsetSpec]:
        if self._resolved_toolset_specs:
            return self._resolved_toolset_specs
        return [ref for ref in self.toolset_refs if isinstance(ref, ToolsetSpec)]

    def resolve_toolsets(self, available: dict[str, ToolsetSpec], context: ToolsetBuildContext) -> None:
        """Resolve toolset refs to specs during registry linking."""
        resolved: list[ToolsetSpec] = []
        for ref in self.toolset_refs:
            if isinstance(ref, str):
                if ref not in available:
                    raise ValueError(f"Entry '{self.name}' references unknown toolset: {ref}. Available: {sorted(available.keys())}")
                resolved.append(available[ref])
            elif isinstance(ref, ToolsetSpec):
                resolved.append(ref)
            else:
                raise TypeError("Entry toolsets must be names or ToolsetSpec instances.")
        self._resolved_toolset_specs = resolved
        self.toolset_context = context

    def __post_init__(self) -> None:
        if self.schema_in is not None and not issubclass(self.schema_in, WorkerArgs):
            raise TypeError(f"schema_in must subclass WorkerArgs; got {self.schema_in}")
        for ref in self.toolset_refs:
            if not isinstance(ref, (str, ToolsetSpec)):
                raise TypeError("Entry toolsets must be names or ToolsetSpec instances.")

    async def call(self, input_args: WorkerArgs, runtime: WorkerRuntimeProtocol) -> Any:
        """Execute the wrapped function."""
        result = self.func(input_args, runtime)
        return await result if inspect.isawaitable(result) else result


def entry(
    name: str | None = None, *, toolsets: list[ToolsetRef] | None = None, schema_in: Optional[Type[WorkerArgs]] = None
) -> Callable[[Callable[..., Any]], EntryFunction]:
    """Decorator to mark a function as an entry point."""
    def decorator(func: Callable[..., Any]) -> EntryFunction:
        return EntryFunction(func=func, entry_name=name or func.__name__, toolset_refs=list(toolsets) if toolsets else [], schema_in=schema_in)
    return decorator


@dataclass
class Worker:
    """An LLM-powered worker that can be run as an entry point."""
    name: str
    instructions: str
    description: str | None = None
    model: str | Model | None = None
    compatible_models: InitVar[list[str] | None] = None
    toolset_specs: list[ToolsetSpec] = field(default_factory=list)
    toolset_context: ToolsetBuildContext | None = None
    builtin_tools: list[Any] = field(default_factory=list)
    model_settings: Optional[ModelSettings] = None
    schema_in: Optional[Type[WorkerArgs]] = None
    schema_out: Optional[Type[BaseModel]] = None

    def __post_init__(self, compatible_models: list[str] | None) -> None:
        if self.schema_in is not None and not issubclass(self.schema_in, WorkerArgs):
            raise TypeError(f"schema_in must subclass WorkerArgs; got {self.schema_in}")
        for spec in self.toolset_specs:
            if not isinstance(spec, ToolsetSpec):
                raise TypeError("Worker toolset_specs must contain ToolsetSpec instances.")
        self.model = select_model(worker_model=self.model, compatible_models=compatible_models, worker_name=self.name)

    def _resolve_toolset_context(self) -> ToolsetBuildContext:
        return self.toolset_context or ToolsetBuildContext(worker_name=self.name)

    def as_toolset_spec(self, *, approval_config: dict[str, dict[str, Any]] | None = None) -> ToolsetSpec:
        """Return a ToolsetSpec that exposes this worker as a tool."""
        def factory(_ctx: ToolsetBuildContext) -> AbstractToolset[Any]:
            toolset = WorkerToolset(worker=self)
            if approval_config is not None:
                set_toolset_approval_config(toolset, approval_config)
            return toolset
        return ToolsetSpec(factory=factory)

    def _build_agent(self, resolved_model: str | Model, runtime: WorkerRuntimeProtocol, *, toolsets: list[AbstractToolset[Any]] | None = None) -> Agent[WorkerRuntimeProtocol, Any]:
        """Build a PydanticAI agent with toolsets passed directly."""
        return Agent(
            model=resolved_model, instructions=self.instructions, output_type=self.schema_out or str,
            deps_type=type(runtime), toolsets=toolsets or None, builtin_tools=self.builtin_tools, end_strategy="exhaustive",
        )

    def _emit_tool_events(
        self, messages: list[Any], runtime: WorkerRuntimeProtocol
    ) -> None:
        """Emit ToolCallEvent/ToolResultEvent for tool calls in messages."""
        if runtime.config.on_event is None:
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
            runtime.config.on_event(ToolCallEvent(
                worker=self.name,
                tool_name=call_part.tool_name,
                tool_call_id=call_id,
                args_json=call_part.args_as_json_str(),
                depth=runtime.frame.depth,
            ))

            return_part = tool_returns.get(call_id)
            if return_part:
                runtime.config.on_event(ToolResultEvent(
                    worker=self.name,
                    depth=runtime.frame.depth,
                    tool_name=call_part.tool_name,
                    tool_call_id=call_id,
                    content=return_part.content,
                ))

    async def call(self, input_data: Any, run_ctx: RunContext[WorkerRuntimeProtocol]) -> Any:
        """Execute the worker with the given input."""
        return await self._call_internal(input_data, run_ctx.deps.config, run_ctx.deps.frame, run_ctx)

    async def _call_internal(
        self,
        input_data: Any,
        config: RuntimeConfig,
        state: CallFrame,
        run_ctx: RunContext[WorkerRuntimeProtocol],
    ) -> Any:
        """Shared worker execution path."""
        input_args = ensure_worker_args(self.schema_in, input_data)
        prompt_spec = input_args.prompt_spec()

        # Check depth limit using global config and per-call state
        if state.depth >= config.max_depth:
            raise RuntimeError(f"Max depth exceeded: {config.max_depth}")

        # model is guaranteed non-None after __post_init__ (select_model raises if missing)
        resolved_model = self.model
        if resolved_model is None:
            raise RuntimeError("Worker model is not set")

        toolset_context = self._resolve_toolset_context()
        async with build_tool_plane(
            toolset_specs=self.toolset_specs,
            toolset_context=toolset_context,
            approval_callback=run_ctx.deps.config.approval_callback,
            return_permission_errors=run_ctx.deps.config.return_permission_errors,
        ) as (_raw_toolsets, wrapped_toolsets):
            attachment_parts: list[BinaryContent] = []
            if prompt_spec.attachments:
                base_for_attachments = run_ctx.deps.config.project_root or Path.cwd()
                for attachment_path in prompt_spec.attachments:
                    resolved_path = _resolve_attachment_path(attachment_path, base_for_attachments)
                    attachment_parts.append(_load_attachment(resolved_path))

            # Fork per-call state and build child runtime for PydanticAI deps
            child_runtime = run_ctx.deps.spawn_child(
                active_toolsets=wrapped_toolsets,
                model=resolved_model,
                invocation_name=self.name,
            )
            child_runtime.frame.prompt = prompt_spec.text
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
        self, agent: Agent[WorkerRuntimeProtocol, Any], prompt: str | Sequence[UserContent],
        runtime: WorkerRuntimeProtocol, message_history: list[Any] | None, *, log_messages: bool = True
    ) -> Any:
        """Run agent with event stream handler for UI updates."""
        from pydantic_ai.messages import PartDeltaEvent

        from .event_parser import parse_event
        emitted_tool_events = False

        async def event_stream_handler(_: RunContext[WorkerRuntimeProtocol], events: AsyncIterable[Any]) -> None:
            nonlocal emitted_tool_events
            async for event in events:
                if runtime.config.verbosity < 2 and isinstance(event, PartDeltaEvent):
                    continue
                runtime_event = parse_event({"worker": self.name, "event": event, "depth": runtime.frame.depth})
                if isinstance(runtime_event, (ToolCallEvent, ToolResultEvent)):
                    emitted_tool_events = True
                if runtime.config.on_event is not None:
                    runtime.config.on_event(runtime_event)

        result = await agent.run(prompt, deps=runtime, model_settings=self.model_settings, event_stream_handler=event_stream_handler, message_history=message_history)
        _finalize_messages(self.name, runtime, None, result, log_messages=log_messages)
        if runtime.config.on_event is not None and not emitted_tool_events:
            self._emit_tool_events(result.new_messages(), runtime)
        return result.output
