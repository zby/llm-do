# Per-Worker Approval Config Semantics

## Context
Ctx runtime review flagged that `_approval_config` mutates shared toolset instances when multiple workers reuse the same Python toolset. We need to decide whether per-worker approval config is supported and, if so, how to avoid cross-worker leakage.

## Findings
- `build_toolsets` currently applies `_approval_config` by mutating existing instances from `ToolsetBuildContext.available_toolsets`, which includes Python toolset instances shared across workers.
- This behavior means the last worker to set `_approval_config` wins globally for that shared toolset instance.
- Approval wrapping now preserves worker fields and cycles, but does not address per-worker config semantics.

## Open Questions
- Do we want to reject non-`_approval_config` keys for shared toolset refs (so worker YAML can’t silently “configure” a shared Python instance)?
- Should “pre_approved” be allowed to bypass toolset-level “blocked” decisions, or should blocks always win?

## Conclusion
We should support **per-worker** `_approval_config` with **per-reference semantics**:

- `_approval_config` under `toolsets.<ref>` applies only to that worker’s *reference* to the toolset/worker named `<ref>` (no cross-worker leakage).
- Shared instances discovered from Python (and referenced `Worker` stubs) remain **singletons**, but their approval config becomes **non-mutating metadata** applied via a wrapper.

**Precedence rules (intended semantics)**
1. Toolset-level “blocked” decisions must win (cannot be bypassed by config).
2. `_approval_config.<tool>.pre_approved: true` skips prompting for that tool call.
3. Otherwise, defer to `needs_approval()` when implemented; else default-deny (needs approval).

**Concrete implementation sketch**

Add a tiny delegating wrapper that carries `_approval_config` without mutating the shared instance:

```python
# llm_do/toolsets/loader.py (or a small helper module)
from typing import Any

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import needs_approval_from_config

class ToolsetRef(AbstractToolset[Any]):
    def __init__(self, inner: AbstractToolset[Any], approval_config: dict[str, dict[str, Any]] | None):
        self.inner = inner
        self._approval_config = approval_config

    @property
    def id(self) -> str | None:
        return getattr(self.inner, "id", None)

    async def get_tools(self, ctx: Any) -> dict:
        return await self.inner.get_tools(ctx)

    async def call_tool(self, name: str, tool_args: dict[str, Any], ctx: Any, tool: Any) -> Any:
        return await self.inner.call_tool(name, tool_args, ctx, tool)

    def needs_approval(self, name: str, tool_args: dict[str, Any], ctx: Any, config: Any = None) -> Any:
        inner_fn = getattr(self.inner, "needs_approval", None)
        if callable(inner_fn):
            return inner_fn(name, tool_args, ctx, config)
        return needs_approval_from_config(name, config)

    def get_approval_description(self, name: str, tool_args: dict[str, Any], ctx: Any) -> str:
        inner_fn = getattr(self.inner, "get_approval_description", None)
        if callable(inner_fn):
            return inner_fn(name, tool_args, ctx)
        args_str = ", ".join(f"{k}={v!r}" for k, v in tool_args.items())
        return f"{name}({args_str})"
```

Then change `build_toolsets` so shared toolset refs never get mutated:

```python
existing = context.available_toolsets.get(toolset_ref)
if existing is not None:
    approval_cfg = toolset_config.get("_approval_config")
    other_keys = set(toolset_config) - {"_approval_config"}
    if other_keys:
        raise TypeError(f"Shared toolset {toolset_ref!r} cannot be configured via worker YAML: {sorted(other_keys)}")
    toolsets.append(ToolsetRef(existing, approval_cfg) if approval_cfg else existing)
    continue
```

**Important:** wrapping a `Worker` reference will hide it from `isinstance(..., Worker)` checks, so approval wrapping must unwrap `ToolsetRef.inner` when recursing into worker toolsets (otherwise nested tool calls won’t be gated).
