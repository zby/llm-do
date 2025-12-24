"""Callable entry implementations for the context runtime.

This module provides:
- WorkerEntry: An LLM-powered worker that IS an AbstractToolset
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Type, TYPE_CHECKING

from pydantic import BaseModel, TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from ..ui.events import TextResponseEvent, ToolCallEvent, ToolResultEvent


class WorkerInput(BaseModel):
    """Input schema for workers."""
    input: str

if TYPE_CHECKING:
    from .ctx import Context

from .ctx import ModelType


def _format_prompt(input_data: Any) -> str:
    """Format input data as a string prompt."""
    if isinstance(input_data, BaseModel):
        return input_data.model_dump_json(indent=2)
    if isinstance(input_data, dict):
        return json.dumps(input_data, indent=2)
    return str(input_data)


@dataclass
class ToolEntry:
    """Wrapper for using a tool from a toolset as an entry point.

    This is used for the code entry pattern where a Python tool function
    is the main entry point instead of a worker.
    """

    toolset: AbstractToolset[Any]
    tool_name: str
    kind: str = "tool"
    model: ModelType | None = None
    requires_approval: bool = False
    toolsets: list[AbstractToolset[Any]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.tool_name

    async def call(self, input_data: Any, ctx: "Context", run_ctx: RunContext["Context"]) -> Any:
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
class WorkerEntry(AbstractToolset[Any]):
    """An LLM-powered worker that is also an AbstractToolset.

    WorkerEntry represents an agent that uses an LLM to process
    prompts and can call tools to accomplish tasks. As an AbstractToolset,
    it can be composed into other workers' toolsets.

    Tools are passed as a list of AbstractToolsets which are combined
    and passed directly to the PydanticAI Agent.
    """

    name: str
    instructions: str
    model: ModelType | None = None
    toolsets: list[AbstractToolset[Any]] = field(default_factory=list)
    model_settings: Optional[ModelSettings] = None
    schema_in: Optional[Type[BaseModel]] = None
    schema_out: Optional[Type[BaseModel]] = None
    requires_approval: bool = False
    kind: str = "worker"

    # AbstractToolset implementation
    @property
    def id(self) -> str | None:
        """Return the worker name as its toolset id."""
        return self.name

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        """Return this worker as a callable tool."""
        description = self.instructions[:200] + "..." if len(self.instructions) > 200 else self.instructions

        tool_def = ToolDefinition(
            name=self.name,
            description=description,
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input prompt for the worker"},
                },
                "required": ["input"],
            },
        )

        return {self.name: ToolsetTool(
            toolset=self,
            tool_def=tool_def,
            max_retries=0,
            args_validator=TypeAdapter(WorkerInput).validator,
        )}

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[Any], tool: ToolsetTool[Any]
    ) -> Any:
        """Execute the worker when called as a tool."""
        return await self.call(tool_args, ctx.deps, ctx)

    def _build_agent(self, resolved_model: ModelType, ctx: "Context") -> Agent["Context", Any]:
        """Build a PydanticAI agent with toolsets passed directly."""
        return Agent(
            model=resolved_model,
            instructions=self.instructions,
            output_type=self.schema_out or str,
            deps_type=type(ctx),
            toolsets=self.toolsets if self.toolsets else None,
            # Use 'exhaustive' to ensure tool calls are executed even when
            # text output is present in the same response
            end_strategy="exhaustive",
        )

    def _emit_tool_events(self, messages: list[Any], ctx: "Context") -> None:
        """Emit ToolCallEvent/ToolResultEvent for tool calls in messages."""
        if ctx.on_event is None:
            return

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

    async def call(self, input_data: Any, ctx: "Context", run_ctx: RunContext["Context"]) -> Any:
        """Execute the worker with the given input."""
        if self.schema_in is not None:
            input_data = self.schema_in.model_validate(input_data)

        # Resolve model: entry's model or context's default
        resolved_model = self.model if self.model is not None else ctx.model

        agent = self._build_agent(resolved_model, ctx)
        prompt = _format_prompt(input_data)

        # Use streaming if verbosity >= 2 and on_event callback is set
        if ctx.verbosity >= 2 and ctx.on_event is not None:
            output = await self._run_streaming(agent, prompt, ctx)
        else:
            result = await agent.run(prompt, deps=ctx, model_settings=self.model_settings)
            self._emit_tool_events(result.new_messages(), ctx)
            output = result.output

        return output

    async def _run_streaming(
        self, agent: Agent["Context", Any], prompt: str, ctx: "Context"
    ) -> Any:
        """Run agent with streaming, emitting text deltas."""
        async with agent.run_stream(prompt, deps=ctx, model_settings=self.model_settings) as stream:
            # Stream text deltas
            async for chunk in stream.stream_text(delta=True):
                if ctx.on_event:
                    ctx.on_event(TextResponseEvent(
                        worker=self.name,
                        content=chunk,
                        is_delta=True,
                    ))

            # Get the final output
            output = await stream.get_output()

            # Emit tool events (must be inside context manager)
            self._emit_tool_events(stream.new_messages(), ctx)

        return output
