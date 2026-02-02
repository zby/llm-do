"""Approval-related toolset wrappers."""
from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Optional

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResult,
    ApprovalToolset,
)

from ..toolsets.approval import get_toolset_approval_config

ApprovalCallback = Callable[[ApprovalRequest], ApprovalDecision | Awaitable[ApprovalDecision]]


@dataclass(frozen=True)
class RunApprovalPolicy:
    """Execution-time approval policy configuration for a run."""
    mode: Literal["prompt", "approve_all", "reject_all"] = "prompt"
    approval_callback: ApprovalCallback | None = None
    return_permission_errors: bool = False
    cache: dict[Any, ApprovalDecision] | None = None


@dataclass(frozen=True)
class AgentApprovalPolicy:
    """Resolved approval policy for an agent invocation."""
    approval_callback: ApprovalCallback
    return_permission_errors: bool = False

    def wrap_toolsets(self, toolsets: list[AbstractToolset[Any]]) -> list[AbstractToolset[Any]]:
        wrapped: list[AbstractToolset[Any]] = []
        for toolset in toolsets:
            if isinstance(toolset, (ApprovalToolset, ApprovalDeniedResultToolset)):
                raise TypeError("Pre-wrapped ApprovalToolset instances are not supported")
            approved: AbstractToolset[Any] = ApprovalContextToolset(
                inner=toolset,
                approval_callback=self.approval_callback,
                config=get_toolset_approval_config(toolset),
            )
            wrapped.append(
                ApprovalDeniedResultToolset(approved)
                if self.return_permission_errors
                else approved
            )
        return wrapped


class ApprovalContextToolset(ApprovalToolset):
    """Approval wrapper that preserves inner toolset context management."""

    async def __aenter__(self) -> "ApprovalContextToolset":
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        return await self._inner.__aexit__(*args)


class ApprovalDeniedResultToolset(AbstractToolset):
    """Return a tool result when a PermissionError occurs."""
    def __init__(self, inner: AbstractToolset):
        self._inner = inner

    @property
    def id(self) -> Optional[str]:
        return getattr(self._inner, "id", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def __aenter__(self) -> "ApprovalDeniedResultToolset":
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        return await self._inner.__aexit__(*args)

    async def get_tools(self, ctx: Any) -> dict:
        return await self._inner.get_tools(ctx)

    async def call_tool(self, name: str, tool_args: dict[str, Any], ctx: Any, tool: Any) -> Any:
        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except PermissionError as exc:
            return {"error": str(exc), "tool_name": name, "error_type": "permission"}


def _default_cache_key(request: ApprovalRequest) -> tuple[str, str]:
    """Return a stable cache key for an ApprovalRequest."""
    try:
        args_json = json.dumps(request.tool_args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        args_json = json.dumps(str(request.tool_args))
    return request.tool_name, args_json


def _ensure_decision(value: Any) -> ApprovalDecision:
    if isinstance(value, ApprovalDecision):
        return value
    raise TypeError("approval_callback must return ApprovalDecision")


def make_headless_approval_callback(*, approve_all: bool, reject_all: bool, deny_note: str = "Use --approve-all for headless") -> ApprovalCallback:
    """Create a deterministic headless approval callback."""
    if approve_all and reject_all:
        raise ValueError("Cannot set both approve_all and reject_all")
    def callback(request: ApprovalRequest) -> ApprovalDecision:
        if approve_all:
            return ApprovalDecision(approved=True)
        return ApprovalDecision(approved=False, note="--reject-all" if reject_all else deny_note)
    return callback


def make_tui_approval_callback(prompt_user: ApprovalCallback, *, approve_all: bool, reject_all: bool, cache: dict[Any, ApprovalDecision] | None = None) -> ApprovalCallback:
    """Wrap an interactive approval callback with session caching."""
    if approve_all and reject_all:
        raise ValueError("Cannot set both approve_all and reject_all")
    session_cache: dict[Any, ApprovalDecision] = {} if cache is None else cache

    async def callback(request: ApprovalRequest) -> ApprovalDecision:
        if approve_all:
            return ApprovalDecision(approved=True)
        if reject_all:
            return ApprovalDecision(approved=False, note="--reject-all")
        cache_key = _default_cache_key(request)
        cached = session_cache.get(cache_key)
        if cached is not None:
            return cached
        decision_or_awaitable = prompt_user(request)
        decision = _ensure_decision(await decision_or_awaitable if inspect.isawaitable(decision_or_awaitable) else decision_or_awaitable)
        if decision.approved and decision.remember == "session":
            session_cache[cache_key] = decision
        return decision

    return callback


def resolve_approval_callback(policy: RunApprovalPolicy) -> ApprovalCallback:
    """Return the concrete approval callback for a policy."""
    if policy.mode == "approve_all":
        return make_headless_approval_callback(approve_all=True, reject_all=False)
    if policy.mode == "reject_all":
        return make_headless_approval_callback(approve_all=False, reject_all=True)
    if policy.mode != "prompt":
        raise ValueError(f"Unknown approval mode: {policy.mode}")
    if policy.approval_callback is None:
        return make_headless_approval_callback(approve_all=False, reject_all=False)
    return make_tui_approval_callback(policy.approval_callback, approve_all=False, reject_all=False, cache=policy.cache)


def wrap_toolsets_for_approval(toolsets: list[AbstractToolset[Any]], approval_callback: ApprovalCallback, *, return_permission_errors: bool = False) -> list[AbstractToolset[Any]]:
    """Wrap toolsets with approval handling."""
    return AgentApprovalPolicy(approval_callback=approval_callback, return_permission_errors=return_permission_errors).wrap_toolsets(toolsets)


def resolve_agent_call_approval(
    runtime_config: Any,
    agent_name: str,
    *,
    has_attachments: bool,
) -> ApprovalResult:
    """Compute whether an agent call should require approval."""
    require_all = getattr(runtime_config, "agent_calls_require_approval", False)
    require_attachments = getattr(
        runtime_config, "agent_attachments_require_approval", False
    )
    overrides = getattr(runtime_config, "agent_approval_overrides", {}) or {}
    override = overrides.get(agent_name)
    if override is not None:
        if override.calls_require_approval is not None:
            require_all = override.calls_require_approval
        if override.attachments_require_approval is not None:
            require_attachments = override.attachments_require_approval
    if require_all:
        return ApprovalResult.needs_approval()
    if has_attachments and require_attachments:
        return ApprovalResult.needs_approval()
    return ApprovalResult.pre_approved()
