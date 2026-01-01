# WorkerRuntime and Approval Design

This note consolidates design thinking around `WorkerRuntime` context injection
and approval wrapping architecture.

---

## 1. Context Injection for Tools

### How Runtime Flows to Tools

- The runtime context is `llm_do.ctx_runtime.WorkerRuntime`.
- Tools receive a `RunContext[WorkerRuntime]` from pydantic-ai. The runtime is
  available as `ctx.deps`.
- Tool schemas are derived from the non-`RunContext` parameters, so the LLM
  never sees the runtime context parameter.
- Nested tool/worker calls use `ctx.deps.call(name, input)`.
- Context access is opt-in by accepting `RunContext[WorkerRuntime]` as the first
  parameter.

### Example

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.ctx_runtime import WorkerRuntime

tools = FunctionToolset()

@tools.tool
async def analyze_config(ctx: RunContext[WorkerRuntime], raw: str) -> str:
    return await ctx.deps.call("config_parser", {"input": raw})
```

---

## 2. Approval Wrapping Architecture

### Current State

- The CLI performs recursive wrapping in `llm_do/ctx_runtime/cli.py:_wrap_toolsets_with_approval`.
- `build_entry()` resolves toolsets and returns a raw entry; `run()` wraps
  toolsets and then builds `WorkerRuntime`. Runtime itself does not wrap.
- The recursion exists because `WorkerInvocable` is both a toolset and an owner
  of its own `toolsets`. Wrapping only the top-level list protects calls to a
  worker but not the internal tool calls inside that worker.
- The wrapper is `ApprovalToolset` from `pydantic_ai_blocking_approval`, which:
  - Calls `needs_approval()` when implemented (e.g., filesystem, shell).
  - Reads optional per-tool `_approval_config`.
  - Uses a shared `ApprovalMemory` and an approval callback (headless or TUI).
- Entry-level approval has been removed; approvals are handled only at the tool
  layer via `ApprovalToolset`.

### Problem

Programmatic users (direct Python runs) must duplicate CLI logic to get the same
approval behavior. This is noisy and error-prone.

### Design Goals

- **Ergonomics**: avoid explicit recursive wrapping in user scripts.
- **Consistency**: match CLI semantics for approvals and error messaging.
- **Separation**: keep approval decisions centralized (headless vs TUI, approve-all vs strict).
- **Safety**: preserve default-deny semantics (unapproved tools must not run).
- **Minimal churn**: avoid large refactors unless the payoff is clear.

---

## 3. Architectural Options

### Option A: Expose a Public Helper

Keep recursion, but hide it behind a small helper.

```python
# llm_do/ctx_runtime/approval.py
def wrap_entry_for_approval(
    entry: ToolEntry | WorkerEntry,
    *,
    approve_all: bool,
    approval_callback: ApprovalCallback | None = None,
    memory: ApprovalMemory | None = None,
) -> ToolEntry | WorkerEntry:
    ...
```

**Pros**: Low risk, minimal change, makes direct Python usage shorter.
**Cons**: Still conceptually a wrapper; does not reduce duplication across code paths.
**When**: Immediate ergonomics without architectural changes.

### Option B: Move Wrapping into `WorkerRuntime.from_entry(...)`

`WorkerRuntime.from_entry` accepts approval configuration and wraps internally.

```python
WorkerRuntime.from_entry(
    entry,
    model=...,
    approval_policy=ApprovalPolicy(mode="approve_all"),
)
```

**Pros**: Removes boilerplate, centralizes approval at the "run" boundary.
**Cons**: Runtime becomes responsible for approval; requires careful ordering.
**When**: Clean programmatic usage without changing toolset creation.

### Option C: Move Wrapping into `build_entry(...)`

Add approval options to `build_entry(...)` so it returns wrapped entries.

```python
entry = await build_entry(
    worker_files, python_files, model, entry_name,
    approval_controller=ApprovalController(mode="approve_all"),
)
```

**Pros**: Ensures every entry from loader is safe by default.
**Cons**: Approval config is runtime-dependent; leaks UI details into loader.
**When**: "Safe by default" entry objects that are ready to run.

### Option D: Lazy Toolset Specs

Keep a declarative spec for toolsets and instantiate wrapped toolsets only when
an approval controller is available.

```python
class ToolsetSpec:
    def build(self, approval_controller, memory, callback) -> AbstractToolset:
        toolset = self.factory(self.config)
        return ApprovalToolset(inner=toolset, ...)
```

**Pros**: True "wrap at creation point", supports different modes cleanly.
**Cons**: Larger refactor affecting discovery, entry resolution, and tests.
**When**: Robust long-term architecture for multiple runtime modes.

### Option E: Move Approval into WorkerRuntime Directly

WorkerRuntime becomes the sole approval gate; no wrapping layer.

```python
class WorkerRuntime:
    def call_tool(...):
        if toolset_has_needs_approval:
            result = toolset.needs_approval(name, args, ctx)
            if result.needs_approval: request_approval(...)
        return toolset.call_tool(...)
```

**Pros**: No wrapping at all; simpler mental model.
**Cons**: Deep change; more coupling between runtime and toolsets.
**When**: Eliminating `ApprovalToolset` as a dependency is acceptable.

---

## 4. Recommended Approach (Option B Variant)

Introduce a small approval policy object and move wrapping into runtime, while
keeping CLI as the policy builder.

### Implementation Steps

1. **New approval policy dataclass** (runtime-level).
   - Fields: `approval_callback`, `return_permission_errors`, `memory`, `mode`.

2. **Shared helper for wrapping**.
   - Move `_wrap_toolsets_with_approval()` to `llm_do/ctx_runtime/approval.py`.
   - Expose `wrap_entry_for_approval(entry, policy) -> entry`.
   - Always recurse into `WorkerInvocable.toolsets`.
   - Skip re-wrapping if `ApprovalToolset` is already present.

3. **Runtime API change**.
   - Add `approval_policy: ApprovalPolicy | None` to `WorkerRuntime.from_entry()`.
   - If policy is provided, runtime wraps entry toolsets before any agent is built.

4. **CLI integration**.
   - `run()` constructs `ApprovalPolicy` from flags/callbacks.
   - Calls `WorkerRuntime.from_entry(..., approval_policy=...)`.
   - CLI no longer performs wrapping itself.

---

## 5. Open Questions

### Context Injection
- Do we want a small Protocol ("ToolContext") to type the minimal surface
  (just `call(...)`) instead of exposing the full `WorkerRuntime`?

### Approval Architecture
- Should runtime always require an approval policy (fail closed) or allow
  `None` for raw toolsets (opt-out for tests and power users)?
- Do we support pre-wrapped toolsets, or is "runtime owns wrapping" a hard rule?
- Should `ApprovalToolset` remain the mechanism, or move approval into
  `WorkerRuntime.call_tool()` directly?
- Where should `ApprovalMemory` live: per-run policy instance, or global?
- Is a future wrapper pipeline needed (logging/tracing), or would that be YAGNI?

---

## 6. Decision Factors

- **Urgency**: Option A or B for near-term ergonomics.
- **Scope tolerance**: Option D/E require non-trivial refactors.
- **API clarity**: Option B offers a clean "one entry point" for runtime config.
- **Architecture direction**: Option D is most future-proof but also most work.

## Conclusion

Context injection is handled by pydantic-ai via `RunContext[WorkerRuntime]`.
Tools opt in by accepting the `RunContext` parameter, and use `ctx.deps` for
nested calls without exposing runtime details to the model schema.

For approval wrapping, Option B (move into `WorkerRuntime.from_entry`) with a
shared helper offers the best balance of ergonomics and minimal churn.
