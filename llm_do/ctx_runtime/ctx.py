"""Context-centric dispatcher for tools and workers.

This module provides the core Context class that orchestrates execution of
tools and workers through:
- Toolset-based dispatch (AbstractToolset)
- Depth tracking to prevent infinite recursion
- Execution tracing for debugging
- Model resolution (entry-level or context-default)
- Event emission for real-time progress updates
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Protocol, TYPE_CHECKING

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage
from pydantic_ai.tools import RunContext

from ..model_compat import select_model
from ..ui.events import UIEvent

if TYPE_CHECKING:
    from .entries import CallableEntry


ModelType = str
ApprovalFn = Callable[["CallableEntry", Any], bool]
EventCallback = Callable[[UIEvent], None]


@dataclass
class CallTrace:
    """Records a single call in the execution trace."""
    name: str
    kind: str
    depth: int
    input_data: Any
    output_data: Any | None = None
    error: str | None = None


class ToolsProxy:
    """Dynamic proxy to call tools by attribute name.

    Enables syntax like `ctx.tools.shell(command="ls")` to invoke tools.
    """

    def __init__(self, ctx: "Context") -> None:
        self._ctx = ctx

    def __getattr__(self, name: str) -> Callable[[Any], Awaitable[Any]]:
        async def _call(**kwargs: Any) -> Any:
            return await self._ctx.call(name, kwargs)

        return _call


class CallableEntry(Protocol):
    """Protocol for entries that can be called via the Context dispatcher."""
    name: str
    kind: str
    requires_approval: bool
    model: ModelType | None

    async def call(self, input_data: Any, ctx: "Context", run_ctx: RunContext["Context"]) -> Any:
        ...


class Context:
    """Dispatches tool calls and manages execution context.

    The Context is the central orchestrator for executing tools and workers.
    It manages:
    - Toolset-based dispatch via ctx.call()
    - Depth tracking to prevent infinite recursion
    - Model resolution (entry's model vs context default)
    - Execution tracing
    - Usage tracking per model
    """

    @classmethod
    def from_entry(
        cls,
        entry: "CallableEntry",
        model: ModelType | None = None,
        *,
        approval: Optional[ApprovalFn] = None,
        max_depth: int = 5,
        on_event: Optional[EventCallback] = None,
        verbosity: int = 0,
    ) -> "Context":
        """Create a Context for running an entry.

        Args:
            entry: The entry to run (WorkerEntry or ToolEntry)
            model: Model override (uses entry.model if not provided)
            approval: Approval callback for tool execution
            max_depth: Maximum call depth
            on_event: Optional callback for UI events (tool calls, streaming text)
            verbosity: Verbosity level (0=quiet, 1=progress, 2=streaming)

        Returns:
            Context configured for the entry
        """
        # Resolve model using model_compat module
        entry_name = getattr(entry, "name", str(entry))
        resolved_model = select_model(
            worker_model=getattr(entry, "model", None),
            cli_model=model,
            compatible_models=getattr(entry, "compatible_models", None),
            worker_name=entry_name,
        )

        # Get toolsets from entry
        toolsets = list(getattr(entry, "toolsets", []) or [])

        return cls(
            toolsets=toolsets,
            model=resolved_model,
            approval=approval,
            max_depth=max_depth,
            on_event=on_event,
            verbosity=verbosity,
        )

    def __init__(
        self,
        toolsets: list[AbstractToolset[Any]],
        model: ModelType,
        *,
        approval: Optional[ApprovalFn] = None,
        max_depth: int = 5,
        depth: int = 0,
        trace: Optional[list[CallTrace]] = None,
        usage: Optional[dict[str, RunUsage]] = None,
        prompt: str = "",
        messages: Optional[list[Any]] = None,
        on_event: Optional[EventCallback] = None,
        verbosity: int = 0,
    ) -> None:
        self.toolsets = toolsets
        self.model = model
        self.approval = approval or (lambda entry, input_data: True)
        self.max_depth = max_depth
        self.depth = depth
        self.trace: list[CallTrace] = trace if trace is not None else []
        self.usage = usage if usage is not None else {}
        self.prompt = prompt
        self.messages = messages if messages is not None else []
        self.tools = ToolsProxy(self)
        self.on_event = on_event
        self.verbosity = verbosity

    def _resolve_model(self, entry: CallableEntry) -> ModelType:
        """Resolve model: entry's model if specified, otherwise context's default."""
        return entry.model if entry.model is not None else self.model

    def _get_usage(self, model: ModelType) -> RunUsage:
        """Get or create RunUsage tracker for a model."""
        key = str(model)
        if key not in self.usage:
            self.usage[key] = RunUsage()
        return self.usage[key]

    def _make_run_context(
        self, tool_name: str, resolved_model: ModelType, deps_ctx: "Context"
    ) -> RunContext["Context"]:
        """Construct a RunContext for direct tool invocation."""
        return RunContext(
            deps=deps_ctx,
            model=resolved_model,
            usage=self._get_usage(resolved_model),
            prompt=self.prompt,
            messages=list(self.messages),
            run_step=deps_ctx.depth,
            retry=0,
            tool_name=tool_name,
        )

    def _child(
        self,
        toolsets: Optional[list[AbstractToolset[Any]]] = None,
    ) -> "Context":
        """Create a child context with incremented depth.

        Note: toolsets are NOT inherited - workers must explicitly specify their tools.
        """
        return Context(
            toolsets if toolsets is not None else self.toolsets,
            model=self.model,
            approval=self.approval,
            max_depth=self.max_depth,
            depth=self.depth + 1,
            trace=self.trace,
            usage=self.usage,
            prompt=self.prompt,
            messages=self.messages,
            on_event=self.on_event,
            verbosity=self.verbosity,
        )

    async def run(self, entry: CallableEntry, input_data: Any) -> Any:
        """Run an entry directly."""
        # Extract prompt from input_data for RunContext
        if isinstance(input_data, dict) and "input" in input_data:
            self.prompt = str(input_data["input"])
        elif isinstance(input_data, str):
            self.prompt = input_data
        return await self._execute(entry, input_data)

    async def call(self, name: str, input_data: Any) -> Any:
        """Call a tool by name (searched across toolsets).

        This enables programmatic tool invocation from code entry points:
            result = await ctx.deps.call("pitch_evaluator", {"input": "..."})
        """
        # Create a temporary run context for get_tools
        run_ctx = self._make_run_context(name, self.model, self)

        # Search for the tool across all toolsets
        for toolset in self.toolsets:
            tools = await toolset.get_tools(run_ctx)
            if name in tools:
                tool = tools[name]
                # Convert input_data to dict if needed
                if not isinstance(input_data, dict):
                    input_data = {"input": input_data}
                result = await toolset.call_tool(name, input_data, run_ctx, tool)
                # Add trace for this call
                trace = CallTrace(name=name, kind="tool", depth=self.depth, input_data=input_data, output_data=result)
                self.trace.append(trace)
                return result

        available = []
        for toolset in self.toolsets:
            tools = await toolset.get_tools(run_ctx)
            available.extend(tools.keys())
        raise KeyError(f"Tool '{name}' not found. Available: {available}")

    async def _execute(self, entry: CallableEntry, input_data: Any) -> Any:
        """Execute an entry with tracing, approval, and child context creation."""
        if self.depth >= self.max_depth:
            raise RuntimeError(f"Max depth exceeded: {self.max_depth}")

        trace = CallTrace(name=entry.name, kind=entry.kind, depth=self.depth, input_data=input_data)
        self.trace.append(trace)

        if entry.requires_approval and not self.approval(entry, input_data):
            trace.error = "approval denied"
            raise PermissionError(f"Approval denied for {entry.name}")

        # Workers get a child context with their declared toolsets
        child_toolsets = list(getattr(entry, "toolsets", []) or [])
        child_ctx = self._child(toolsets=child_toolsets)
        resolved_model = self._resolve_model(entry)
        run_ctx = self._make_run_context(entry.name, resolved_model, child_ctx)

        try:
            result = await entry.call(input_data, child_ctx, run_ctx)
            trace.output_data = result
            return result
        except Exception as exc:
            trace.error = str(exc)
            raise
