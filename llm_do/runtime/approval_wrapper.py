"""Capability-based approval wrapper for toolsets."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence, runtime_checkable

from pydantic_ai import RunContext
from pydantic_ai.toolsets import (
    AbstractToolset,
    CombinedToolset,
    ToolsetTool,
    WrapperToolset,
)
from pydantic_ai_blocking_approval import (
    ApprovalCallback,
    ApprovalConfig,
    ApprovalResult,
    ApprovalToolset,
    SupportsApprovalDescription,
    SupportsNeedsApproval,
    needs_approval_from_config,
)

from ..toolsets.approval import get_toolset_approval_config

ApprovalPolicy = Callable[
    [str, dict[str, Any], RunContext[Any], ApprovalConfig, set[str]],
    ApprovalResult | Awaitable[ApprovalResult],
]
CapabilityProvider = Callable[
    [str, dict[str, Any], RunContext[Any], ApprovalConfig],
    set[str] | Sequence[str] | Awaitable[set[str] | Sequence[str]],
]


@runtime_checkable
class SupportsCapabilities(Protocol):
    """Protocol for toolsets that provide capability information."""

    def get_capabilities(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        config: ApprovalConfig,
    ) -> set[str] | Sequence[str] | Awaitable[set[str] | Sequence[str]]: ...


def _normalize_caps(value: set[str] | Sequence[str] | None) -> set[str]:
    """Normalize capability value to a set."""
    if not value:
        return set()
    return set(value)


async def _toolset_capabilities(
    inner: AbstractToolset[Any],
    name: str,
    tool_args: dict[str, Any],
    ctx: RunContext[Any],
    cfg: ApprovalConfig,
) -> set[str]:
    """Extract capabilities from a toolset if it supports them."""
    toolset: AbstractToolset[Any] | None = None
    if isinstance(inner, SupportsCapabilities):
        toolset = inner
    else:
        tools = await inner.get_tools(ctx)
        tool = tools.get(name)
        if tool is not None and isinstance(tool.toolset, SupportsCapabilities):
            toolset = tool.toolset

    if toolset is None:
        return set()

    result = toolset.get_capabilities(name, tool_args, ctx, cfg)
    if inspect.isawaitable(result):
        result = await result
    return _normalize_caps(result)


@dataclass
class CapabilityPolicyToolset(
    WrapperToolset, SupportsNeedsApproval, SupportsApprovalDescription
):
    """Wraps a toolset with capability-based approval policy."""

    approval_policy: ApprovalPolicy
    capability_provider: CapabilityProvider
    config: ApprovalConfig

    async def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        config: ApprovalConfig,
    ) -> ApprovalResult:
        """Determine if approval is needed based on capabilities."""
        capabilities = self.capability_provider(name, tool_args, ctx, config)
        if inspect.isawaitable(capabilities):
            capabilities = await capabilities
        caps = _normalize_caps(capabilities)
        result = self.approval_policy(name, tool_args, ctx, config, caps)
        if inspect.isawaitable(result):
            result = await result
        return result

    def get_approval_description(
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[Any]
    ) -> str:
        """Get a human-readable description for approval UI."""
        if isinstance(self.wrapped, SupportsApprovalDescription):
            return self.wrapped.get_approval_description(name, tool_args, ctx)

        args_str = ", ".join(f"{key}={value!r}" for key, value in tool_args.items())
        capabilities = self.capability_provider(name, tool_args, ctx, self.config)
        if inspect.isawaitable(capabilities):
            return f"{name}({args_str})"
        caps = _normalize_caps(capabilities)
        if caps:
            caps_label = ", ".join(sorted(caps))
            return f"{name}({args_str}) [caps: {caps_label}]"
        return f"{name}({args_str})"

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        """Forward tool call to wrapped toolset."""
        return await self.wrapped.call_tool(name, tool_args, ctx, tool)


class ApprovalToolsetWithContext(ApprovalToolset):
    """ApprovalToolset that properly delegates context manager and visitor methods."""

    async def __aenter__(self) -> "ApprovalToolsetWithContext":
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        return await self._inner.__aexit__(*args)

    def apply(self, visitor: Callable[[AbstractToolset[Any]], None]) -> None:
        self._inner.apply(visitor)

    def visit_and_replace(
        self, visitor: Callable[[AbstractToolset[Any]], AbstractToolset[Any]]
    ) -> AbstractToolset[Any]:
        replaced = self._inner.visit_and_replace(visitor)
        if replaced is self._inner:
            return self
        return ApprovalToolsetWithContext(
            inner=replaced,
            approval_callback=self._approval_callback,
            config=self.config,
        )


class ApprovalDeniedResultToolset(AbstractToolset[Any]):
    """Wraps a toolset to return error results instead of raising PermissionError."""

    def __init__(self, inner: AbstractToolset[Any]) -> None:
        self._inner = inner

    @property
    def id(self) -> str | None:
        return getattr(self._inner, "id", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        return await self._inner.get_tools(ctx)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except PermissionError as exc:
            return {"error": str(exc), "tool_name": name, "error_type": "permission"}


def wrap_toolsets_with_capabilities(
    *,
    toolsets: list[AbstractToolset[Any]],
    approval_callback: ApprovalCallback | None,
    approval_config: ApprovalConfig | None,
    capability_rules: Mapping[str, str] | None,
    capability_map: Mapping[str, Sequence[str]] | None,
    capability_default: str,
    approval_policy: ApprovalPolicy | None = None,
    return_permission_errors: bool = False,
) -> list[AbstractToolset[Any]]:
    """Wrap toolsets with capability-based approval.

    Args:
        toolsets: The toolsets to wrap
        approval_callback: Callback for approval decisions
        approval_config: Per-tool approval configuration
        capability_rules: Maps capability names to approval rules
        capability_map: Maps tool names to capability sets
        capability_default: Default rule for unknown capabilities
        approval_policy: Custom policy function (optional)
        return_permission_errors: Return errors instead of raising

    Returns:
        List of wrapped toolsets
    """
    if not toolsets:
        return []
    if approval_callback is None:
        return toolsets

    config = approval_config or {}
    capabilities = capability_map or {}
    rules = capability_rules or {}
    inner = CombinedToolset(toolsets)

    async def capability_provider(
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        cfg: ApprovalConfig,
    ) -> set[str]:
        """Collect capabilities from all sources."""
        caps: set[str] = set()
        # From capability map
        if name in capabilities:
            caps.update(capabilities[name])
        # From per-tool config
        entry = cfg.get(name, {})
        declared = entry.get("capabilities")
        if declared:
            if isinstance(declared, str):
                caps.add(declared)
            else:
                caps.update(declared)
        # From toolset implementation
        caps.update(await _toolset_capabilities(inner, name, tool_args, ctx, cfg))
        return caps

    def policy_from_rules(
        name: str,
        _tool_args: dict[str, Any],
        _ctx: RunContext[Any],
        cfg: ApprovalConfig,
        caps: set[str],
    ) -> ApprovalResult:
        """Apply capability rules to determine approval."""
        entry = cfg.get(name, {})
        if entry.get("blocked"):
            reason = entry.get("block_reason") or "Blocked by approval policy"
            return ApprovalResult.blocked(reason)
        if entry.get("pre_approved"):
            return ApprovalResult.pre_approved()

        if caps:
            blocked = [
                cap for cap in caps if rules.get(cap, capability_default) == "blocked"
            ]
            if blocked:
                return ApprovalResult.blocked(f"Capability blocked: {blocked[0]}")
            if any(
                rules.get(cap, capability_default) == "needs_approval" for cap in caps
            ):
                return ApprovalResult.needs_approval()
            if any(
                rules.get(cap, capability_default) == "pre_approved" for cap in caps
            ):
                return ApprovalResult.pre_approved()

        return needs_approval_from_config(name, cfg)

    policy = approval_policy or policy_from_rules
    policy_toolset = CapabilityPolicyToolset(
        wrapped=inner,
        approval_policy=policy,
        capability_provider=capability_provider,
        config=config,
    )
    approved: AbstractToolset[Any] = ApprovalToolsetWithContext(
        inner=policy_toolset,
        approval_callback=approval_callback,
        config=config,
    )

    if return_permission_errors:
        approved = ApprovalDeniedResultToolset(approved)

    return [approved]


def wrap_toolsets_simple(
    toolsets: list[AbstractToolset[Any]],
    approval_callback: ApprovalCallback,
    *,
    return_permission_errors: bool = False,
) -> list[AbstractToolset[Any]]:
    """Simple approval wrapping without capability-based policy.

    This uses the per-toolset approval config from get_toolset_approval_config().
    """
    wrapped: list[AbstractToolset[Any]] = []
    for toolset in toolsets:
        if isinstance(toolset, (ApprovalToolset, ApprovalDeniedResultToolset)):
            raise TypeError("Pre-wrapped ApprovalToolset instances are not supported")
        config = get_toolset_approval_config(toolset)
        approved: AbstractToolset[Any] = ApprovalToolset(
            inner=toolset,
            approval_callback=approval_callback,
            config=config,
        )
        if return_permission_errors:
            approved = ApprovalDeniedResultToolset(approved)
        wrapped.append(approved)
    return wrapped
