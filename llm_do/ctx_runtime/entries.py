"""Callable entry implementations for the context runtime.

This module provides:
- ToolEntry: Wraps a PydanticAI Tool for use in the context runtime
- WorkerEntry: An LLM-powered worker that can use tools
- ToolsetToolEntry: Wraps individual tools from AbstractToolset
- tool_entry: Decorator to create a ToolEntry from a function
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type, TYPE_CHECKING

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model, KnownModelName
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext, Tool, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

if TYPE_CHECKING:
    from .ctx import CallTrace, Context


class WorkerToolset(AbstractToolset[Any]):
    """Wraps a WorkerEntry as an AbstractToolset for unified discovery."""

    def __init__(self, worker: "WorkerEntry") -> None:
        self._worker = worker

    @property
    def id(self) -> str | None:
        return self._worker.name

    @property
    def worker(self) -> "WorkerEntry":
        return self._worker

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        # Not used directly - expand_toolset_to_entries handles WorkerToolset specially
        return {}

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[Any], tool: ToolsetTool[Any]
    ) -> Any:
        return await self._worker.call(tool_args, ctx.deps, ctx)


ModelType = Model | KnownModelName


def _format_prompt(input_data: Any) -> str:
    """Format input data as a string prompt."""
    if isinstance(input_data, BaseModel):
        return input_data.model_dump_json(indent=2)
    if isinstance(input_data, dict):
        return json.dumps(input_data, indent=2)
    return str(input_data)


@dataclass
class ToolEntry:
    """Wraps a PydanticAI Tool for use in the context runtime.

    This entry type allows PydanticAI tools to be called through
    the Context dispatcher with proper validation and tracing.
    """

    tool: Tool["Context"]
    requires_approval: bool = False
    kind: str = "tool"
    model: ModelType | None = None  # tools don't use models, but protocol requires it

    @property
    def name(self) -> str:
        return self.tool.name

    async def call(self, input_data: Any, ctx: "Context", run_ctx: RunContext["Context"]) -> Any:
        """Call the tool with the provided input data."""
        # Convert to dict if needed
        if isinstance(input_data, BaseModel):
            input_data = input_data.model_dump()
        elif not isinstance(input_data, dict):
            raise TypeError(f"Expected dict or BaseModel, got {type(input_data)}")

        # Validate input using the tool's schema
        validated = self.tool.function_schema.validator.validate_python(input_data)

        # Call the underlying function with RunContext and validated args
        if self.tool.function_schema.takes_ctx:
            result = self.tool.function(run_ctx, **validated)
        else:
            result = self.tool.function(**validated)

        # Await if async
        if hasattr(result, "__await__"):
            result = await result

        return result


def tool_entry(
    name: str | None = None,
    *,
    requires_approval: bool = False,
) -> Callable[[Callable[..., Any]], ToolEntry]:
    """Decorator to create a ToolEntry from a function with PydanticAI signature.

    Args:
        name: Optional tool name (defaults to function name)
        requires_approval: Whether the tool requires approval

    Returns:
        Decorator that creates a ToolEntry
    """

    def decorator(func: Callable[..., Any]) -> ToolEntry:
        tool_name = name or func.__name__
        pydantic_tool = Tool(func, name=tool_name, requires_approval=requires_approval)
        return ToolEntry(
            tool=pydantic_tool,
            requires_approval=requires_approval,
        )

    return decorator


@dataclass
class ToolsetToolEntry:
    """Wraps an individual tool from an AbstractToolset.

    This enables toolset tools to be registered in the Context registry
    and called through the normal dispatch mechanism. Each tool from
    a toolset becomes a separate ToolsetToolEntry.
    """

    toolset: AbstractToolset[Any]
    tool_name: str
    tool_def: ToolDefinition
    requires_approval: bool = False
    kind: str = "tool"
    model: ModelType | None = None
    # Original Tool object (for FunctionToolset) - preserves function_schema for LLM
    _original_tool: Tool[Any] | None = None

    @property
    def name(self) -> str:
        return self.tool_name

    async def call(self, input_data: Any, ctx: "Context", run_ctx: RunContext["Context"]) -> Any:
        """Call the toolset tool with the provided input data.

        Delegates to the toolset's call_tool method after getting
        the ToolsetTool wrapper for proper validation.
        """
        # Convert to dict if needed
        if isinstance(input_data, BaseModel):
            input_data = input_data.model_dump()
        elif not isinstance(input_data, dict):
            raise TypeError(f"Expected dict or BaseModel, got {type(input_data)}")

        # Get the ToolsetTool wrapper for this tool
        tools = await self.toolset.get_tools(run_ctx)
        tool = tools.get(self.tool_name)
        if tool is None:
            raise KeyError(f"Tool {self.tool_name} not found in toolset")

        # Delegate to toolset's call_tool
        return await self.toolset.call_tool(self.tool_name, input_data, run_ctx, tool)


@dataclass
class WorkerEntry:
    """An LLM-powered worker that can use tools.

    WorkerEntry represents an agent that uses an LLM to process
    prompts and can call tools to accomplish tasks.
    """

    name: str
    instructions: str
    model: ModelType | None = None
    tools: list["ToolsetToolEntry"] = field(default_factory=list)
    model_settings: Optional[ModelSettings] = None
    schema_in: Optional[Type[BaseModel]] = None
    schema_out: Optional[Type[BaseModel]] = None
    requires_approval: bool = False
    kind: str = "worker"

    def _collect_tools(self, ctx: "Context") -> list[Tool[Any]]:
        """Collect PydanticAI tools from entries."""
        tools: list[Tool[Any]] = []
        for entry in self.tools:
            if isinstance(entry, ToolEntry):
                takes_ctx = entry.tool.function_schema.takes_ctx
                if takes_ctx:
                    async def _tool_proxy(
                        run_ctx: RunContext[Any],
                        _entry_name: str = entry.name,
                        **kwargs: Any,
                    ) -> Any:
                        return await run_ctx.deps.call(_entry_name, kwargs)
                else:
                    async def _tool_proxy(
                        _entry_name: str = entry.name,
                        **kwargs: Any,
                    ) -> Any:
                        return await ctx.call(_entry_name, kwargs)

                _tool_proxy.__name__ = entry.name
                _tool_proxy.__doc__ = entry.tool.description or entry.tool.function_schema.description
                tools.append(Tool(
                    _tool_proxy,
                    name=entry.name,
                    description=entry.tool.description,
                    requires_approval=entry.requires_approval,
                    function_schema=entry.tool.function_schema,
                ))
            elif isinstance(entry, ToolsetToolEntry):
                # For toolset tools (including workers via WorkerToolset),
                # create a proxy that calls through context
                async def _toolset_proxy(
                    run_ctx: RunContext[Any],
                    _entry_name: str = entry.name,
                    **kwargs: Any,
                ) -> Any:
                    return await run_ctx.deps.call(_entry_name, kwargs)

                _toolset_proxy.__name__ = entry.name
                _toolset_proxy.__doc__ = entry.tool_def.description

                # Use original tool's schema if available (from FunctionToolset)
                if entry._original_tool is not None:
                    tools.append(Tool(
                        _toolset_proxy,
                        name=entry.name,
                        description=entry.tool_def.description,
                        requires_approval=entry.requires_approval,
                        function_schema=entry._original_tool.function_schema,
                    ))
                else:
                    # For non-FunctionToolset (including WorkerToolset)
                    tools.append(Tool(
                        _toolset_proxy,
                        name=entry.name,
                        description=entry.tool_def.description,
                        requires_approval=entry.requires_approval,
                    ))
        return tools

    def _build_agent(self, resolved_model: ModelType, ctx: "Context") -> Agent["Context", Any]:
        """Build a PydanticAI agent with tools registered."""
        return Agent(
            model=resolved_model,
            instructions=self.instructions,
            output_type=self.schema_out or str,
            deps_type=type(ctx),
            tools=self._collect_tools(ctx),
        )

    def _extract_tool_traces(
        self, messages: list[Any], depth: int, existing_trace: list["CallTrace"]
    ) -> list["CallTrace"]:
        """Extract tool call traces from PydanticAI messages."""
        from .ctx import CallTrace
        traces: list[CallTrace] = []

        # Collect tool calls and their returns
        tool_calls: dict[str, ToolCallPart] = {}
        tool_returns: dict[str, ToolReturnPart] = {}

        for msg in messages:
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ToolCallPart):
                        tool_calls[part.tool_call_id] = part
            elif isinstance(msg, ModelRequest):
                for part in msg.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_returns[part.tool_call_id] = part

        # Track (name, args_json) pairs already traced via ctx.call() at this depth
        # This allows repeated calls with different args to be traced
        def _trace_key(name: str, args: Any) -> tuple[str, str]:
            args_json = json.dumps(args, sort_keys=True) if args else ""
            return (name, args_json)

        already_traced = {
            _trace_key(t.name, t.input_data)
            for t in existing_trace if t.depth == depth
        }

        # Create traces by matching calls with returns (skip only exact duplicates)
        for call_id, call_part in tool_calls.items():
            key = _trace_key(call_part.tool_name, call_part.args)
            if key in already_traced:
                continue
            already_traced.add(key)  # Prevent duplicates within this batch too
            return_part = tool_returns.get(call_id)
            traces.append(CallTrace(
                name=call_part.tool_name,
                kind="tool",
                depth=depth,
                input_data=call_part.args,
                output_data=return_part.content if return_part else None,
            ))

        return traces

    async def call(self, input_data: Any, ctx: "Context", run_ctx: RunContext["Context"]) -> Any:
        """Execute the worker with the given input."""
        if self.schema_in is not None:
            input_data = self.schema_in.model_validate(input_data)

        # Resolve model: entry's model or context's default
        resolved_model = self.model if self.model is not None else ctx.model

        agent = self._build_agent(resolved_model, ctx)
        prompt = _format_prompt(input_data)
        result = await agent.run(prompt, deps=ctx, model_settings=self.model_settings)

        # Extract and append tool traces from PydanticAI messages (skip duplicates)
        tool_traces = self._extract_tool_traces(result.new_messages(), ctx.depth, ctx.trace)
        ctx.trace.extend(tool_traces)

        return result.output
