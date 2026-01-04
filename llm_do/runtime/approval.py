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
    ApprovalToolset,
)

ApprovalCallback = Callable[
    [ApprovalRequest],
    ApprovalDecision | Awaitable[ApprovalDecision],
]


@dataclass(frozen=True)
class RunApprovalPolicy:
    """Execution-time approval policy configuration for a run."""

    mode: Literal["prompt", "approve_all", "reject_all"] = "prompt"
    approval_callback: ApprovalCallback | None = None
    return_permission_errors: bool = False
    cache: dict[Any, ApprovalDecision] | None = None
    cache_key_fn: Callable[[ApprovalRequest], Any] | None = None


@dataclass(frozen=True)
class WorkerApprovalPolicy:
    """Resolved approval policy for a worker invocation."""

    approval_callback: ApprovalCallback
    return_permission_errors: bool = False
    approval_configs: dict[str, dict[str, Any]] | None = None

    def wrap_toolsets(
        self,
        toolsets: list[AbstractToolset[Any]],
    ) -> list[AbstractToolset[Any]]:
        wrapped: list[AbstractToolset[Any]] = []
        approval_configs = self.approval_configs or {}

        for toolset in toolsets:
            if isinstance(toolset, (ApprovalToolset, ApprovalDeniedResultToolset)):
                raise TypeError("Pre-wrapped ApprovalToolset instances are not supported")
            toolset_id = getattr(toolset, "id", None)
            config = approval_configs.get(toolset_id) if toolset_id else None
            approved_toolset: AbstractToolset[Any] = ApprovalToolset(
                inner=toolset,
                approval_callback=self.approval_callback,
                config=config,
            )
            if self.return_permission_errors:
                approved_toolset = ApprovalDeniedResultToolset(approved_toolset)
            wrapped.append(approved_toolset)
        return wrapped


class ApprovalDeniedResultToolset(AbstractToolset):
    """Return a tool result when a PermissionError occurs.

    This is used to keep interactive runs alive and let the model observe
    approval denials or permission failures instead of aborting the run.
    """

    def __init__(self, inner: AbstractToolset):
        self._inner = inner

    @property
    def id(self) -> Optional[str]:
        return getattr(self._inner, "id", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def get_tools(self, ctx: Any) -> dict:
        return await self._inner.get_tools(ctx)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: Any,
    ) -> Any:
        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except PermissionError as exc:
            return {
                "error": str(exc),
                "tool_name": name,
                "error_type": "permission",
            }


def _default_cache_key(request: ApprovalRequest) -> tuple[str, str]:
    """Return a stable cache key for an ApprovalRequest.

    Excludes the human-facing description so cache hits survive prompt text changes.
    """
    try:
        args_json = json.dumps(request.tool_args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        args_json = json.dumps(str(request.tool_args))
    return request.tool_name, args_json


def _ensure_decision(value: Any) -> ApprovalDecision:
    if isinstance(value, ApprovalDecision):
        return value
    raise TypeError("approval_callback must return ApprovalDecision")


def make_headless_approval_callback(
    *,
    approve_all: bool,
    reject_all: bool,
    deny_note: str = "Use --approve-all for headless",
) -> ApprovalCallback:
    """Create a deterministic headless approval callback.

    Headless mode never prompts; it either approves everything (--approve-all),
    rejects everything (--reject-all), or rejects approvals by default.
    """
    if approve_all and reject_all:
        raise ValueError("Cannot set both approve_all and reject_all")

    def callback(request: ApprovalRequest) -> ApprovalDecision:
        if approve_all:
            return ApprovalDecision(approved=True)
        if reject_all:
            return ApprovalDecision(approved=False, note="--reject-all")
        return ApprovalDecision(approved=False, note=deny_note)

    return callback


def make_tui_approval_callback(
    prompt_user: ApprovalCallback,
    *,
    approve_all: bool,
    reject_all: bool,
    cache: dict[Any, ApprovalDecision] | None = None,
    cache_key_fn: Callable[[ApprovalRequest], Any] = _default_cache_key,
) -> ApprovalCallback:
    """Wrap an interactive approval callback with session caching.

    Caches approvals only when the returned decision includes
    `remember="session"`.
    """
    if approve_all and reject_all:
        raise ValueError("Cannot set both approve_all and reject_all")

    session_cache: dict[Any, ApprovalDecision] = {} if cache is None else cache

    async def callback(request: ApprovalRequest) -> ApprovalDecision:
        if approve_all:
            return ApprovalDecision(approved=True)
        if reject_all:
            return ApprovalDecision(approved=False, note="--reject-all")

        cache_key = cache_key_fn(request)
        cached = session_cache.get(cache_key)
        if cached is not None:
            return cached

        decision_or_awaitable = prompt_user(request)
        if inspect.isawaitable(decision_or_awaitable):
            decision = _ensure_decision(await decision_or_awaitable)
        else:
            decision = _ensure_decision(decision_or_awaitable)

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

    return make_tui_approval_callback(
        policy.approval_callback,
        approve_all=False,
        reject_all=False,
        cache=policy.cache,
        cache_key_fn=policy.cache_key_fn or _default_cache_key,
    )


def wrap_toolsets_for_approval(
    toolsets: list[AbstractToolset[Any]],
    run_approval_policy: RunApprovalPolicy,
    approval_configs: dict[str, dict[str, Any]] | None = None,
) -> list[AbstractToolset[Any]]:
    """Wrap toolsets with approval handling.

    Called at Invocable.call() time (Worker or ToolInvocable) to ensure
    LLM tool calls go through approval.
    """
    worker_policy = WorkerApprovalPolicy(
        approval_callback=resolve_approval_callback(run_approval_policy),
        return_permission_errors=run_approval_policy.return_permission_errors,
        approval_configs=approval_configs,
    )
    return worker_policy.wrap_toolsets(toolsets)


