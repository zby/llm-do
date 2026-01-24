"""Entry implementations: AgentEntry, EntryToolset, EntryFunction."""
from __future__ import annotations

import inspect
from contextlib import contextmanager, nullcontext
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterable, Callable, Optional, Sequence, Type

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import (
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

from ..models import NULL_MODEL, select_model
from ..toolsets.approval import set_toolset_approval_config
from ..toolsets.loader import ToolsetBuildContext, ToolsetSpec, instantiate_toolsets
from ..toolsets.validators import DictValidator
from .approval import wrap_toolsets_for_approval
from .args import (
    Attachment,
    PromptContent,
    WorkerArgs,
    get_display_text,
    has_attachments,
    normalize_input,
    render_prompt,
)
from .call import CallConfig, CallFrame, CallScope
from .contracts import CallRuntimeProtocol
from .deps import CallRuntime
from .events import ToolCallEvent, ToolResultEvent, UserMessageEvent
from .shared import RuntimeConfig

if TYPE_CHECKING:
    from .shared import Runtime


def _should_use_message_history(runtime: CallRuntimeProtocol) -> bool:
    """Only use message history for the top-level entry run."""
    return runtime.frame.config.depth == 0


def _get_all_messages(result: Any) -> list[Any]:
    """Return all messages from a run result or stream object."""
    return list(result.all_messages())


def _finalize_messages(
    entry_name: str,
    runtime: CallRuntimeProtocol,
    result: Any,
    *,
    log_messages: bool = True,
) -> list[Any]:
    """Log and sync message history using a single message snapshot."""
    messages = _get_all_messages(result)
    if log_messages:
        runtime.log_messages(entry_name, runtime.frame.config.depth, messages)
    if _should_use_message_history(runtime):
        runtime.frame.messages[:] = messages
    return messages


class _MessageLogList(list):
    """List that logs new messages as they are appended."""

    def __init__(self, runtime: CallRuntimeProtocol, entry_name: str, depth: int) -> None:
        super().__init__()
        self._runtime = runtime
        self._entry_name = entry_name
        self._depth = depth
        self._logged_count = 0

    def _log_new_messages(self, start: int) -> None:
        for message in list(self)[start:]:
            self._runtime.log_messages(self._entry_name, self._depth, [message])
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
    runtime: CallRuntimeProtocol, *, entry_name: str, depth: int
) -> Any:
    """Capture and log messages as they are appended for this run."""
    from pydantic_ai._agent_graph import capture_run_messages, get_captured_run_messages

    with capture_run_messages():
        try:
            run_messages = get_captured_run_messages()
        except LookupError:
            yield
            return
        run_messages.messages = _MessageLogList(runtime, entry_name, depth)
        yield


class _DefaultEntryToolSchema(BaseModel):
    """Default schema for entries exposed as tools."""

    input: str
    attachments: list[str] = []


def build_entry_tool(entry: "AgentEntry", toolset: AbstractToolset[Any]) -> ToolsetTool[Any]:
    """Build a ToolsetTool for exposing an entry as a callable tool."""
    desc = entry.description or entry.instructions
    desc = desc[:200] + "..." if len(desc) > 200 else desc
    schema = entry.schema_in or _DefaultEntryToolSchema
    return ToolsetTool(
        toolset=toolset,
        tool_def=ToolDefinition(
            name=entry.name,
            description=desc,
            parameters_json_schema=schema.model_json_schema(),
        ),
        max_retries=0,
        args_validator=DictValidator(schema),
    )


@dataclass
class EntryToolset(AbstractToolset[Any]):
    """Adapter that exposes an entry as a single tool for another agent."""

    entry: "AgentEntry"

    @property
    def id(self) -> str | None:
        return self.entry.name

    def _messages_from_args(
        self, tool_args: dict[str, Any]
    ) -> list[PromptContent] | None:
        """Extract prompt messages from tool args, or None if parsing fails."""
        try:
            _, messages = normalize_input(self.entry.schema_in, tool_args)
            return messages
        except Exception:
            return None

    def _get_attachment_paths(self, tool_args: dict[str, Any]) -> list[str]:
        """Extract attachment paths from tool args for approval display."""
        messages = self._messages_from_args(tool_args)
        if messages is not None:
            return [str(p.path) for p in messages if isinstance(p, Attachment)]
        # Fallback: check raw tool_args for attachments field
        raw_attachments = tool_args.get("attachments") or []
        return list(raw_attachments)

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

        messages = self._messages_from_args(tool_args)
        has_attach = (
            has_attachments(messages)
            if messages is not None
            else bool(tool_args.get("attachments"))
        )
        if has_attach and require_attachments:
            return ApprovalResult.needs_approval()
        return ApprovalResult.pre_approved()

    def get_approval_description(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
    ) -> str:
        attachment_paths = self._get_attachment_paths(tool_args)
        if attachment_paths:
            attachment_list = ", ".join(attachment_paths)
            return f"Call entry {name} with attachments: {attachment_list}"
        return f"Call entry {name}"

    async def get_tools(self, run_ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        return {self.entry.name: build_entry_tool(self.entry, self)}

    async def call_tool(self, name: str, tool_args: dict[str, Any], run_ctx: RunContext[Any], tool: ToolsetTool[Any]) -> Any:
        return await self.entry.call(tool_args, run_ctx)


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

    def start(
        self,
        runtime: "Runtime",
        *,
        message_history: list[Any] | None = None,
    ) -> CallScope:
        toolset_context = self.toolset_context or ToolsetBuildContext(
            worker_name=self.name
        )
        toolsets = instantiate_toolsets(self.toolset_specs, toolset_context)
        wrapped_toolsets = wrap_toolsets_for_approval(
            toolsets,
            runtime.config.approval_callback,
            return_permission_errors=runtime.config.return_permission_errors,
        )
        call_config = CallConfig.build(
            wrapped_toolsets,
            model=NULL_MODEL,
            depth=0,
            invocation_name=self.name,
        )
        frame = CallFrame(
            config=call_config,
            messages=list(message_history) if message_history else [],
        )
        call_runtime = CallRuntime(runtime=runtime, frame=frame)
        return CallScope(entry=self, runtime=call_runtime, toolsets=toolsets)

    async def run_turn(
        self,
        scope: CallScope,
        input_data: Any,
    ) -> Any:
        input_args, messages = normalize_input(self.schema_in, input_data)
        display_text = get_display_text(messages)
        runtime = scope.runtime
        runtime.frame.prompt = display_text
        if runtime.config.on_event is not None and runtime.frame.config.depth == 0:
            runtime.config.on_event(
                UserMessageEvent(
                    worker=self.name,
                    content=display_text,
                )
            )
        return await self.call(input_args, messages, scope)

    async def call(
        self,
        input_args: WorkerArgs | None,
        messages: list[PromptContent],
        scope: CallScope,
    ) -> Any:
        """Execute the wrapped function."""
        first_arg = input_args if input_args is not None else messages
        result = self.func(first_arg, scope)
        return await result if inspect.isawaitable(result) else result


def entry(
    name: str | None = None, *, toolsets: list[ToolsetRef] | None = None, schema_in: Optional[Type[WorkerArgs]] = None
) -> Callable[[Callable[..., Any]], EntryFunction]:
    """Decorator to mark a function as an entry point."""
    def decorator(func: Callable[..., Any]) -> EntryFunction:
        return EntryFunction(func=func, entry_name=name or func.__name__, toolset_refs=list(toolsets) if toolsets else [], schema_in=schema_in)
    return decorator


@dataclass
class AgentEntry:
    """An LLM-powered entry that can be run as a call scope."""

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
                raise TypeError("Entry toolset_specs must contain ToolsetSpec instances.")
        self.model = select_model(worker_model=self.model, compatible_models=compatible_models, worker_name=self.name)

    def _resolve_toolset_context(self) -> ToolsetBuildContext:
        return self.toolset_context or ToolsetBuildContext(worker_name=self.name)

    def as_toolset_spec(self, *, approval_config: dict[str, dict[str, Any]] | None = None) -> ToolsetSpec:
        """Return a ToolsetSpec that exposes this entry as a tool."""
        def factory(_ctx: ToolsetBuildContext) -> AbstractToolset[Any]:
            toolset = EntryToolset(entry=self)
            if approval_config is not None:
                set_toolset_approval_config(toolset, approval_config)
            return toolset
        return ToolsetSpec(factory=factory)

    def _build_toolsets(
        self, config: RuntimeConfig
    ) -> tuple[list[AbstractToolset[Any]], list[AbstractToolset[Any]]]:
        toolset_context = self._resolve_toolset_context()
        toolsets = instantiate_toolsets(self.toolset_specs, toolset_context)
        wrapped_toolsets = wrap_toolsets_for_approval(
            toolsets,
            config.approval_callback,
            return_permission_errors=config.return_permission_errors,
        )
        return toolsets, wrapped_toolsets

    def start(
        self,
        runtime: "Runtime",
        *,
        message_history: list[Any] | None = None,
    ) -> CallScope:
        """Start a top-level call scope for this entry."""
        resolved_model = self.model
        if resolved_model is None:
            raise RuntimeError("Entry model is not set")

        toolsets, wrapped_toolsets = self._build_toolsets(runtime.config)
        call_config = CallConfig.build(
            wrapped_toolsets,
            model=resolved_model,
            depth=0,
            invocation_name=self.name,
        )
        frame = CallFrame(
            config=call_config,
            messages=list(message_history) if message_history else [],
        )
        call_runtime = CallRuntime(runtime=runtime, frame=frame)
        return CallScope(entry=self, runtime=call_runtime, toolsets=toolsets)

    def _start_child(self, parent_runtime: CallRuntimeProtocol) -> CallScope:
        """Start a nested call scope for this entry."""
        if parent_runtime.frame.config.depth >= parent_runtime.config.max_depth:
            raise RuntimeError(
                f"Max depth exceeded calling '{self.name}': "
                f"depth {parent_runtime.frame.config.depth} >= max {parent_runtime.config.max_depth}"
            )

        resolved_model = self.model
        if resolved_model is None:
            raise RuntimeError("Entry model is not set")

        toolsets, wrapped_toolsets = self._build_toolsets(parent_runtime.config)
        child_runtime = parent_runtime.spawn_child(
            active_toolsets=wrapped_toolsets,
            model=resolved_model,
            invocation_name=self.name,
        )
        return CallScope(entry=self, runtime=child_runtime, toolsets=toolsets)

    def _build_agent(self, resolved_model: str | Model, runtime: CallRuntimeProtocol, *, toolsets: list[AbstractToolset[Any]] | None = None) -> Agent[CallRuntimeProtocol, Any]:
        """Build a PydanticAI agent with toolsets passed directly."""
        return Agent(
            model=resolved_model, instructions=self.instructions, output_type=self.schema_out or str,
            deps_type=type(runtime), toolsets=toolsets or None, builtin_tools=self.builtin_tools, end_strategy="exhaustive",
        )

    def _emit_tool_events(
        self, messages: list[Any], runtime: CallRuntimeProtocol
    ) -> None:
        """Emit ToolCallEvent/ToolResultEvent for tool calls in messages."""
        if runtime.config.on_event is None:
            return

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

        for call_id, call_part in tool_calls.items():
            runtime.config.on_event(ToolCallEvent(
                worker=self.name,
                tool_name=call_part.tool_name,
                tool_call_id=call_id,
                args_json=call_part.args_as_json_str(),
                depth=runtime.frame.config.depth,
            ))

            return_part = tool_returns.get(call_id)
            if return_part:
                runtime.config.on_event(ToolResultEvent(
                    worker=self.name,
                    depth=runtime.frame.config.depth,
                    tool_name=call_part.tool_name,
                    tool_call_id=call_id,
                    content=return_part.content,
                ))

    async def call(self, input_data: Any, run_ctx: RunContext[CallRuntimeProtocol]) -> Any:
        """Execute the entry with the given input."""
        scope = self._start_child(run_ctx.deps)
        try:
            return await scope.run_turn(input_data)
        finally:
            await scope.close()

    async def run_turn(
        self,
        scope: CallScope,
        input_data: Any,
    ) -> Any:
        """Run a single turn for an active call scope."""
        _, messages = normalize_input(self.schema_in, input_data)

        display_text = get_display_text(messages)
        runtime = scope.runtime
        runtime.frame.prompt = display_text
        if runtime.config.on_event is not None and runtime.frame.config.depth == 0:
            runtime.config.on_event(
                UserMessageEvent(
                    worker=self.name,
                    content=display_text,
                )
            )

        resolved_model = self.model
        if resolved_model is None:
            raise RuntimeError("Entry model is not set")

        agent = self._build_agent(
            resolved_model,
            runtime,
            toolsets=list(runtime.frame.config.active_toolsets),
        )
        base_path = runtime.config.project_root or Path.cwd()
        prompt = render_prompt(messages, base_path)
        message_history = (
            list(runtime.frame.messages)
            if _should_use_message_history(runtime) and runtime.frame.messages
            else None
        )

        use_incremental_log = runtime.config.message_log_callback is not None
        log_context = (
            _capture_message_log(runtime, entry_name=self.name, depth=runtime.frame.config.depth)
            if use_incremental_log
            else nullcontext()
        )

        with log_context:
            if runtime.config.on_event is not None:
                output = await self._run_with_event_stream(
                    agent,
                    prompt,
                    runtime,
                    message_history,
                    log_messages=not use_incremental_log,
                )
            else:
                result = await agent.run(
                    prompt,
                    deps=runtime,
                    model_settings=self.model_settings,
                    message_history=message_history,
                )
                _finalize_messages(
                    self.name,
                    runtime,
                    result,
                    log_messages=not use_incremental_log,
                )
                output = result.output

        return output

    async def _run_with_event_stream(
        self, agent: Agent[CallRuntimeProtocol, Any], prompt: str | Sequence[UserContent],
        runtime: CallRuntimeProtocol, message_history: list[Any] | None, *, log_messages: bool = True
    ) -> Any:
        """Run agent with event stream handler for UI updates."""
        from pydantic_ai.messages import PartDeltaEvent

        from .event_parser import parse_event
        emitted_tool_events = False

        async def event_stream_handler(_: RunContext[CallRuntimeProtocol], events: AsyncIterable[Any]) -> None:
            nonlocal emitted_tool_events
            async for event in events:
                if runtime.config.verbosity < 2 and isinstance(event, PartDeltaEvent):
                    continue
                runtime_event = parse_event({"worker": self.name, "event": event, "depth": runtime.frame.config.depth})
                if isinstance(runtime_event, (ToolCallEvent, ToolResultEvent)):
                    emitted_tool_events = True
                if runtime.config.on_event is not None:
                    runtime.config.on_event(runtime_event)

        result = await agent.run(prompt, deps=runtime, model_settings=self.model_settings, event_stream_handler=event_stream_handler, message_history=message_history)
        _finalize_messages(self.name, runtime, result, log_messages=log_messages)
        if runtime.config.on_event is not None and not emitted_tool_events:
            self._emit_tool_events(result.new_messages(), runtime)
        return result.output
