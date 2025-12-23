"""Context-centric dispatcher for tools and workers (experiment)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Protocol

from pydantic_ai.models import Model, KnownModelName
from pydantic_ai.usage import Usage
from pydantic_ai.tools import RunContext

from registry import Registry


ModelType = Model | KnownModelName
ApprovalFn = Callable[["CallableEntry", Any], bool]


@dataclass
class CallTrace:
    name: str
    kind: str
    depth: int
    input_data: Any
    output_data: Any | None = None
    error: str | None = None


class ToolsProxy:
    """Dynamic proxy to call tools by attribute name."""

    def __init__(self, ctx: "Context") -> None:
        self._ctx = ctx

    def __getattr__(self, name: str) -> Callable[[Any], Awaitable[Any]]:
        async def _call(**kwargs: Any) -> Any:
            return await self._ctx.call(name, kwargs)

        return _call


class CallableEntry(Protocol):
    name: str
    kind: str
    requires_approval: bool
    model: ModelType | None

    async def call(self, input_data: Any, ctx: "Context", run_ctx: RunContext["Context"]) -> Any:
        ...


class Context:
    """Dispatches registry calls and enforces approvals + depth."""

    @classmethod
    def from_tool_entries(
        cls,
        entries: list["CallableEntry"],
        model: ModelType,
        *,
        approval: Optional[ApprovalFn] = None,
        max_depth: int = 5,
    ) -> "Context":
        registry = Registry()
        for entry in entries:
            registry.register(entry)
        return cls(registry, model=model, approval=approval, max_depth=max_depth)

    @classmethod
    def from_worker(
        cls,
        worker: "CallableEntry",
        model: ModelType | None = None,
        *,
        approval: Optional[ApprovalFn] = None,
        max_depth: int = 5,
    ) -> "Context":
        registry = Registry()
        tools = getattr(worker, "tools", [])
        for entry in tools:
            registry.register(entry)
        registry.register(worker)
        # Use worker's model if no explicit model provided
        resolved_model = model or worker.model
        if resolved_model is None:
            raise ValueError("Model must be provided either to Context or Worker")
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
    ) -> None:
        self.registry = registry
        self.model = model
        self.approval = approval or (lambda entry, input_data: True)
        self.max_depth = max_depth
        self.depth = depth
        self.trace = trace if trace is not None else []
        self.usage = usage if usage is not None else {}
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

    def _make_run_context(self, tool_name: str, resolved_model: ModelType) -> RunContext["Context"]:
        """Construct a RunContext for direct tool invocation."""
        return RunContext(
            deps=self,
            model=resolved_model,
            usage=self._get_usage(resolved_model),
            prompt="",
            messages=[],
            run_step=self.depth,
            retry=0,
            tool_name=tool_name,
        )

    def _child(self) -> "Context":
        """Create a child context with incremented depth."""
        return Context(
            self.registry,
            model=self.model,
            approval=self.approval,
            max_depth=self.max_depth,
            depth=self.depth + 1,
            trace=self.trace,
            usage=self.usage,
        )

    async def call(self, name: str, input_data: Any) -> Any:
        if self.depth >= self.max_depth:
            raise RuntimeError(f"Max depth exceeded: {self.max_depth}")

        entry = self.registry.get(name)
        trace = CallTrace(name=entry.name, kind=entry.kind, depth=self.depth, input_data=input_data)
        self.trace.append(trace)

        if entry.requires_approval and not self.approval(entry, input_data):
            trace.error = "approval denied"
            raise PermissionError(f"Approval denied for {entry.name}")

        child_ctx = self._child()
        resolved_model = self._resolve_model(entry)
        run_ctx = self._make_run_context(name, resolved_model)

        try:
            result = await entry.call(input_data, child_ctx, run_ctx)
            trace.output_data = result
            return result
        except Exception as exc:
            trace.error = str(exc)
            raise
