"""Approval-related toolset wrappers."""
from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any, Literal, Optional

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalToolset,
)

from .worker import ToolInvocable, Worker

ApprovalCallback = Callable[
    [ApprovalRequest],
    ApprovalDecision | Awaitable[ApprovalDecision],
]


@dataclass(frozen=True)
class ApprovalPolicy:
    """Execution-time approval policy configuration."""

    mode: Literal["prompt", "approve_all", "reject_all"] = "prompt"
    approval_callback: ApprovalCallback | None = None
    return_permission_errors: bool = False
    cache: dict[Any, ApprovalDecision] | None = None
    cache_key_fn: Callable[[ApprovalRequest], Any] | None = None


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


def resolve_approval_callback(policy: ApprovalPolicy) -> ApprovalCallback:
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


def _wrap_toolsets_with_approval(
    toolsets: list[AbstractToolset[Any]],
    approval_callback: ApprovalCallback,
    return_permission_errors: bool = False,
    _visited_workers: dict[int, Worker] | None = None,
) -> list[AbstractToolset[Any]]:
    """Wrap toolsets with ApprovalToolset for approval handling.

    ApprovalToolset auto-detects if the inner toolset has needs_approval()
    and delegates to it. Otherwise it uses optional config and defaults to
    "needs approval" (secure by default).

    Recurses into nested Worker.toolsets so tool calls inside delegated
    workers are also gated.
    """
    wrapped: list[AbstractToolset[Any]] = []
    if _visited_workers is None:
        _visited_workers = {}

    def wrap_worker(worker: Worker, callback: ApprovalCallback) -> Worker:
        existing = _visited_workers.get(id(worker))
        if existing is not None:
            return existing
        wrapped_worker = replace(worker, toolsets=[])
        _visited_workers[id(worker)] = wrapped_worker
        if worker.toolsets:
            wrapped_worker.toolsets = _wrap_toolsets_with_approval(
                worker.toolsets,
                callback,
                return_permission_errors=return_permission_errors,
                _visited_workers=_visited_workers,
            )
        return wrapped_worker

    for toolset in toolsets:
        approved_toolset: AbstractToolset[Any]
        # Avoid double-wrapping toolsets that already have approval handling.
        if isinstance(toolset, ApprovalToolset):
            inner = getattr(toolset, "_inner", None)
            if isinstance(inner, Worker):
                inner_callback = getattr(toolset, "_approval_callback", approval_callback)
                wrapped_inner = wrap_worker(inner, inner_callback)
                if wrapped_inner is not inner:
                    toolset = ApprovalToolset(
                        inner=wrapped_inner,
                        approval_callback=inner_callback,
                        config=getattr(toolset, "config", None),
                    )
            approved_toolset = toolset
            if return_permission_errors:
                approved_toolset = ApprovalDeniedResultToolset(approved_toolset)
            wrapped.append(approved_toolset)
            continue

        # Recursively wrap toolsets inside Worker
        if isinstance(toolset, Worker):
            toolset = wrap_worker(toolset, approval_callback)

        # Get any stored approval config from the toolset
        config = getattr(toolset, "_approval_config", None)

        # Wrap all toolsets with ApprovalToolset (secure by default)
        # - Toolsets with needs_approval() method: ApprovalToolset delegates to it
        # - Toolsets with _approval_config: uses config for per-tool pre-approval
        # - Other toolsets: all tools require approval unless config pre-approves
        approved_toolset = ApprovalToolset(
            inner=toolset,
            approval_callback=approval_callback,
            config=config,
        )
        if return_permission_errors:
            approved_toolset = ApprovalDeniedResultToolset(approved_toolset)
        wrapped.append(approved_toolset)

    return wrapped


def wrap_entry_for_approval(
    entry: Any,
    approval_policy: ApprovalPolicy,
) -> Any:
    """Return entry with toolsets wrapped for approval handling.

    This wraps only the entry's toolsets; the entry invocation itself is trusted
    and is not approval-gated for code-entry tools.
    """
    toolsets = list(getattr(entry, "toolsets", []) or [])
    if not toolsets:
        return entry

    callback = resolve_approval_callback(approval_policy)
    wrapped_toolsets = _wrap_toolsets_with_approval(
        toolsets,
        callback,
        return_permission_errors=approval_policy.return_permission_errors,
    )

    if isinstance(entry, Worker):
        return replace(entry, toolsets=wrapped_toolsets)
    if isinstance(entry, ToolInvocable):
        return replace(entry, toolsets=wrapped_toolsets)
    return entry
