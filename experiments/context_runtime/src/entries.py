"""Callable entry implementations (experiment)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model, KnownModelName
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext, Tool

from .ctx import CallableEntry, CallTrace, Context, ModelType


def _format_prompt(input_data: Any) -> str:
    if isinstance(input_data, BaseModel):
        return input_data.model_dump_json(indent=2)
    if isinstance(input_data, dict):
        return json.dumps(input_data, indent=2)
    return str(input_data)


@dataclass
class ToolEntry:
    """Wraps a PydanticAI Tool for use in the context runtime."""

    tool: Tool[Context]
    requires_approval: bool = False
    kind: str = "tool"
    model: ModelType | None = None  # tools don't use models, but protocol requires it

    @property
    def name(self) -> str:
        return self.tool.name

    async def call(self, input_data: Any, ctx: Context, run_ctx: RunContext[Context]) -> Any:
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
    """Decorator to create a ToolEntry from a function with PydanticAI signature."""

    def decorator(func: Callable[..., Any]) -> ToolEntry:
        tool_name = name or func.__name__
        pydantic_tool = Tool(func, name=tool_name, requires_approval=requires_approval)
        return ToolEntry(
            tool=pydantic_tool,
            requires_approval=requires_approval,
        )

    return decorator


@dataclass
class WorkerEntry:
    """An LLM-powered worker that can use tools."""

    name: str
    instructions: str
    model: ModelType | None = None
    tools: list[CallableEntry] = field(default_factory=list)
    model_settings: Optional[ModelSettings] = None
    schema_in: Optional[Type[BaseModel]] = None
    schema_out: Optional[Type[BaseModel]] = None
    requires_approval: bool = False
    kind: str = "worker"

    def _collect_tools(self, ctx: Context) -> list[Tool[Context]]:
        """Collect PydanticAI tools from entries."""
        tools: list[Tool[Context]] = []
        for entry in self.tools:
            if isinstance(entry, ToolEntry):
                takes_ctx = entry.tool.function_schema.takes_ctx
                if takes_ctx:
                    async def _tool_proxy(
                        run_ctx: RunContext[Context],
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
            else:
                # For nested workers, create a wrapper tool that accepts any kwargs
                async def _worker_tool(
                    run_ctx: RunContext[Context],
                    _entry_name: str = entry.name,
                    **kwargs: Any,
                ) -> Any:
                    return await run_ctx.deps.call(_entry_name, kwargs)

                _worker_tool.__name__ = entry.name
                _worker_tool.__doc__ = getattr(entry, "instructions", f"Call {entry.name}")
                tools.append(Tool(_worker_tool, name=entry.name))
        return tools

    def _build_agent(self, resolved_model: ModelType, ctx: Context) -> Agent[Context, Any]:
        """Build a PydanticAI agent with tools registered."""
        return Agent(
            model=resolved_model,
            instructions=self.instructions,
            output_type=self.schema_out or str,
            deps_type=Context,
            tools=self._collect_tools(ctx),
        )

    def _extract_tool_traces(
        self, messages: list[Any], depth: int, existing_trace: list[CallTrace]
    ) -> list[CallTrace]:
        """Extract tool call traces from PydanticAI messages."""
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

        # Names already traced via ctx.call() at this depth
        already_traced = {t.name for t in existing_trace if t.depth == depth}

        # Create traces by matching calls with returns (skip duplicates)
        for call_id, call_part in tool_calls.items():
            if call_part.tool_name in already_traced:
                continue
            return_part = tool_returns.get(call_id)
            traces.append(CallTrace(
                name=call_part.tool_name,
                kind="tool",
                depth=depth,
                input_data=call_part.args,
                output_data=return_part.content if return_part else None,
            ))

        return traces

    async def call(self, input_data: Any, ctx: Context, run_ctx: RunContext[Context]) -> Any:
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
