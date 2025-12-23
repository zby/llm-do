"""Context-centric dispatcher for tools and workers.

This module provides the core Context class that orchestrates execution of
tools and workers through a registry-based dispatch system with:
- Approval enforcement via ApprovalFn callback
- Depth tracking to prevent infinite recursion
- Execution tracing for debugging
- Model resolution (entry-level or context-default)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Protocol, TYPE_CHECKING

from pydantic_ai.models import Model, KnownModelName
from pydantic_ai.usage import Usage
from pydantic_ai.tools import RunContext

from .registry import Registry
from ..model_compat import select_model

if TYPE_CHECKING:
    from .entries import CallableEntry


ModelType = Model | KnownModelName
ApprovalFn = Callable[["CallableEntry", Any], bool]


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
    """Dispatches registry calls and enforces approvals + depth.

    The Context is the central orchestrator for executing tools and workers.
    It manages:
    - Registry lookups for named entries
    - Approval enforcement via callback
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
        available: Optional[list["CallableEntry"]] = None,
        *,
        approval: Optional[ApprovalFn] = None,
        max_depth: int = 5,
    ) -> "Context":
        """Create a Context for running an entry.

        Args:
            entry: The entry to run (WorkerEntry or ToolsetToolEntry)
            model: Model override (uses entry.model if not provided)
            available: Entries to put in registry (uses entry.tools if not provided)
            approval: Approval callback for tool execution
            max_depth: Maximum call depth

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

        # Registry: use available if provided, else entry.tools
        registry = Registry()
        entries = available if available is not None else getattr(entry, "tools", []) or []
        for e in entries:
            registry.register(e)

        return cls(registry, model=resolved_model, approval=approval, max_depth=max_depth)

    def __init__(
        self,
        registry: Registry,
        model: ModelType,
        *,
        approval: Optional[ApprovalFn] = None,
        max_depth: int = 5,
        depth: int = 0,
        trace: Optional[list[CallTrace]] = None,
        usage: Optional[dict[str, Usage]] = None,
        prompt: str = "",
        messages: Optional[list[Any]] = None,
    ) -> None:
        self.registry = registry
        self.model = model
        self.approval = approval or (lambda entry, input_data: True)
        self.max_depth = max_depth
        self.depth = depth
        self.trace = trace if trace is not None else []
        self.usage = usage if usage is not None else {}
        self.prompt = prompt
        self.messages = messages if messages is not None else []
        self.tools = ToolsProxy(self)

    def _resolve_model(self, entry: CallableEntry) -> ModelType:
        """Resolve model: entry's model if specified, otherwise context's default."""
        return entry.model if entry.model is not None else self.model

    def _get_usage(self, model: ModelType) -> Usage:
        """Get or create Usage tracker for a model."""
        key = str(model)
        if key not in self.usage:
            self.usage[key] = Usage()
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

    def _child(self, registry: Optional[Registry] = None) -> "Context":
        """Create a child context with incremented depth and optionally restricted registry."""
        return Context(
            registry if registry is not None else self.registry,
            model=self.model,
            approval=self.approval,
            max_depth=self.max_depth,
            depth=self.depth + 1,
            trace=self.trace,
            usage=self.usage,
            prompt=self.prompt,
            messages=self.messages,
        )

    async def run(self, entry: CallableEntry, input_data: Any) -> Any:
        """Run an entry directly (no registry lookup needed)."""
        # Extract prompt from input_data for RunContext
        if isinstance(input_data, dict) and "input" in input_data:
            self.prompt = str(input_data["input"])
        elif isinstance(input_data, str):
            self.prompt = input_data
        return await self._execute(entry, input_data)

    async def call(self, name: str, input_data: Any) -> Any:
        """Call an entry by name (looked up in registry)."""
        entry = self.registry.get(name)
        return await self._execute(entry, input_data)

    async def _execute(self, entry: CallableEntry, input_data: Any) -> Any:
        """Execute an entry with tracing, approval, and child context creation."""
        if self.depth >= self.max_depth:
            raise RuntimeError(f"Max depth exceeded: {self.max_depth}")

        trace = CallTrace(name=entry.name, kind=entry.kind, depth=self.depth, input_data=input_data)
        self.trace.append(trace)

        if entry.requires_approval and not self.approval(entry, input_data):
            trace.error = "approval denied"
            raise PermissionError(f"Approval denied for {entry.name}")

        # Workers get a child context with registry restricted to their declared tools
        # If entry has a tools attribute, use only those tools (empty list = no tools)
        child_registry: Registry | None = None
        if hasattr(entry, "tools"):
            child_registry = Registry()
            for tool_entry in entry.tools or []:
                child_registry.register(tool_entry)

        child_ctx = self._child(registry=child_registry)
        resolved_model = self._resolve_model(entry)
        run_ctx = self._make_run_context(entry.name, resolved_model, child_ctx)

        try:
            result = await entry.call(input_data, child_ctx, run_ctx)
            trace.output_data = result
            return result
        except Exception as exc:
            trace.error = str(exc)
            raise
