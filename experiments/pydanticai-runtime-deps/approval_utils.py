from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence, runtime_checkable

from pydantic_ai import RunContext
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset, ToolsetTool, WrapperToolset
from pydantic_ai_blocking_approval import (
    ApprovalCallback,
    ApprovalConfig,
    ApprovalResult,
    ApprovalToolset,
    SupportsApprovalDescription,
    SupportsNeedsApproval,
    needs_approval_from_config,
)


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
    def get_capabilities(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        config: ApprovalConfig,
    ) -> set[str] | Sequence[str] | Awaitable[set[str] | Sequence[str]]:
        ...


@dataclass
class CapabilityPolicyToolset(WrapperToolset, SupportsNeedsApproval, SupportsApprovalDescription):
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
        capabilities = self.capability_provider(name, tool_args, ctx, config)
        if inspect.isawaitable(capabilities):
            capabilities = await capabilities
        caps = _normalize_caps(capabilities)
        policy_result = self.approval_policy(name, tool_args, ctx, config, caps)
        if inspect.isawaitable(policy_result):
            policy_result = await policy_result
        toolset_result = await _toolset_needs_approval(self.wrapped, name, tool_args, ctx, config)
        return _merge_approval_results(toolset_result, policy_result)

    def get_approval_description(self, name: str, tool_args: dict[str, Any], ctx: RunContext[Any]) -> str:
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
        self, name: str, tool_args: dict[str, Any], ctx: RunContext[Any], tool: ToolsetTool[Any]
    ) -> Any:
        return await self.wrapped.call_tool(name, tool_args, ctx, tool)


class ApprovalToolsetWithContext(ApprovalToolset):
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


def wrap_toolsets_for_approval(
    *,
    toolsets: Sequence[AbstractToolset[Any]],
    approval_callback: ApprovalCallback | None,
    approval_config: ApprovalConfig | None,
    capability_rules: Mapping[str, str] | None,
    capability_map: Mapping[str, Sequence[str]] | None,
    capability_default: str,
    approval_policy: ApprovalPolicy | None = None,
) -> Sequence[AbstractToolset[Any]] | None:
    if approval_callback is None:
        return None

    config = approval_config or {}
    capabilities = capability_map or {}
    rules = capability_rules or {}

    async def capability_provider(
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        cfg: ApprovalConfig,
    ) -> set[str]:
        caps: set[str] = set()
        if name in capabilities:
            caps.update(capabilities[name])
        entry = cfg.get(name, {})
        declared = entry.get("capabilities")
        if declared:
            if isinstance(declared, str):
                caps.add(declared)
            else:
                caps.update(declared)
        caps.update(await _toolset_capabilities(inner, name, tool_args, ctx, cfg))
        return caps

    def policy_from_rules(
        name: str,
        _tool_args: dict[str, Any],
        _ctx: RunContext[Any],
        cfg: ApprovalConfig,
        caps: set[str],
    ) -> ApprovalResult:
        entry = cfg.get(name, {})
        if entry.get("blocked"):
            reason = entry.get("block_reason") or "Blocked by approval policy"
            return ApprovalResult.blocked(reason)
        if entry.get("pre_approved"):
            return ApprovalResult.pre_approved()

        if caps:
            blocked = [cap for cap in caps if rules.get(cap, capability_default) == "blocked"]
            if blocked:
                return ApprovalResult.blocked(f"Capability blocked: {blocked[0]}")
            if any(rules.get(cap, capability_default) == "needs_approval" for cap in caps):
                return ApprovalResult.needs_approval()
            if any(rules.get(cap, capability_default) == "pre_approved" for cap in caps):
                return ApprovalResult.pre_approved()

        return needs_approval_from_config(name, cfg)

    policy = approval_policy or policy_from_rules
    inner = CombinedToolset(list(toolsets))
    policy_toolset = CapabilityPolicyToolset(
        wrapped=inner,
        approval_policy=policy,
        capability_provider=capability_provider,
        config=config,
    )
    approved = ApprovalToolsetWithContext(
        inner=policy_toolset,
        approval_callback=approval_callback,
        config=config,
    )
    return [approved]


def _normalize_caps(value: set[str] | Sequence[str] | None) -> set[str]:
    if not value:
        return set()
    return set(value)


def _merge_approval_results(
    toolset_result: ApprovalResult | None,
    policy_result: ApprovalResult,
) -> ApprovalResult:
    if toolset_result is None:
        return policy_result
    if toolset_result.is_blocked:
        return toolset_result
    if policy_result.is_blocked:
        return policy_result
    if toolset_result.is_needs_approval or policy_result.is_needs_approval:
        return ApprovalResult.needs_approval()
    return ApprovalResult.pre_approved()


async def _toolset_needs_approval(
    inner: AbstractToolset[Any],
    name: str,
    tool_args: dict[str, Any],
    ctx: RunContext[Any],
    cfg: ApprovalConfig,
) -> ApprovalResult | None:
    toolset: AbstractToolset[Any] | None = None
    if isinstance(inner, SupportsNeedsApproval):
        toolset = inner
    else:
        tools = await inner.get_tools(ctx)
        tool = tools.get(name)
        if tool is not None and isinstance(tool.toolset, SupportsNeedsApproval):
            toolset = tool.toolset

    if toolset is None:
        return None

    result = toolset.needs_approval(name, tool_args, ctx, cfg)
    if inspect.isawaitable(result):
        result = await result
    return result


async def _toolset_capabilities(
    inner: AbstractToolset[Any],
    name: str,
    tool_args: dict[str, Any],
    ctx: RunContext[Any],
    cfg: ApprovalConfig,
) -> set[str]:
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
