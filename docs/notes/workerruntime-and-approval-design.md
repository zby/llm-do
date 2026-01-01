# WorkerRuntime and Approval Design

Design note covering `WorkerRuntime` context injection and approval wrapping.

Dynamic worker creation/invocation is split out into
`docs/notes/dynamic-workers-runtime-design.md`.

---

## 1. Current State

### Context Injection

Context injection is **implemented and working**:

- The runtime context is `llm_do.ctx_runtime.WorkerRuntime`.
- Tools receive a `RunContext[WorkerRuntime]` from pydantic-ai. The runtime is
  available as `ctx.deps`.
- Tool schemas are derived from the non-`RunContext` parameters, so the LLM
  never sees the runtime context parameter.
- Nested tool/worker calls use `ctx.deps.call(name, input)`.
- Context access is opt-in by accepting `RunContext[WorkerRuntime]` as the first
  parameter.

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.ctx_runtime import WorkerRuntime

tools = FunctionToolset()

@tools.tool
async def analyze_config(ctx: RunContext[WorkerRuntime], raw: str) -> str:
    return await ctx.deps.call("config_parser", {"input": raw})
```

### Approval Wrapping

Approval wrapping is **implemented but has ergonomics issues**:

- The CLI performs recursive wrapping in `llm_do/ctx_runtime/cli.py:_wrap_toolsets_with_approval`.
- `build_entry()` resolves toolsets and returns a raw entry; `run()` wraps
  toolsets and then builds `WorkerRuntime`. Runtime itself does not wrap.
- The recursion exists because `WorkerInvocable` is both a toolset and an owner
  of its own `toolsets`. Wrapping only the top-level list protects calls to a
  worker but not the internal tool calls inside that worker.
- The wrapper is `ApprovalToolset` from `pydantic_ai_blocking_approval`, which:
  - Calls `needs_approval()` when implemented (e.g., filesystem, shell).
  - Reads optional per-tool `_approval_config`.
  - Uses an approval callback (headless or TUI), optionally wrapped with session caching.
- Entry-level approval has been removed; approvals are handled only at the tool
  layer via `ApprovalToolset`.

---

## 2. Requirements

### Approval Wrapping

**Problem**: Programmatic users (direct Python runs) must duplicate CLI logic to
get the same approval behavior. This is noisy and error-prone.

**Goals**:
- **Ergonomics**: avoid explicit recursive wrapping in user scripts.
- **Consistency**: match CLI semantics for approvals and error messaging.
- **Separation**: keep approval decisions centralized (headless vs TUI, approve-all vs strict).
- **Safety**: preserve default-deny semantics (unapproved tools must not run).
- **Minimal churn**: avoid large refactors unless the payoff is clear.

---

## 3. Proposed Changes

### Canonical Pipeline (Compiler Framing)

The approval-wrapping debate is mostly about **phase boundaries**. Without a
canonical “compile pipeline”, it’s easy for responsibilities to drift across
CLI / runtime / loaders and the duplication problem reappears.

Treat `llm-do` as a small compiler:

- **Input**: `.worker` files, Python toolsets, CLI overrides, runtime policy
  (model override, approval mode/callback, UI/event callbacks).
- **Output**: an executable `WorkerInvocable | ToolInvocable` ready to run in a
  `WorkerRuntime`.

Introduce a minimal internal representation (`EntryIR`) and a pass pipeline:

**`EntryIR` (minimal)**
- Selected entry name + entry kind (worker/tool).
- Parsed worker files (frontmatter + instructions) and their source paths.
- Discovered Python toolsets/workers and their source paths.
- Worker graph: worker → list of toolset refs (including worker refs).
- Toolset configs, including per-reference `_approval_config` (see `docs/notes/per-worker-approval-config.md`).
- Server-side tool configs.
- Any diagnostics collected during compilation (missing refs, name conflicts, etc.).

**Pass pipeline (suggested)**
1. **Load**: parse `.worker`, load Python modules, discover toolsets/workers.
2. **Resolve**: build the worker/tool graph and resolve toolset refs to objects.
3. **Approval plan**: apply per-reference approval config semantics and decide
   which toolsets need wrapping (policy is injected here).
4. **Wrap**: produce the executable entry with `ApprovalToolset` applied (and any
   other execution wrappers like “return PermissionError as tool result”).
5. **Execute**: create `WorkerRuntime` and run the entry.

**Why this helps**
- CLI and programmatic usage call the same **compile** pass (no re-implementing
  recursive wrapping logic).
- Approval stays a pass over IR, not an ad-hoc behavior sprinkled across loaders.
- Dynamic workers can reuse the same compile passes (create → compile → register → call).
  See `docs/notes/dynamic-workers-runtime-design.md`.

### Approval Wrapping Options

**Option A: Expose a Public Helper**

Keep recursion, but hide it behind a small helper.

```python
# llm_do/ctx_runtime/approval.py
def wrap_entry_for_approval(
    entry: ToolInvocable | WorkerInvocable,
    *,
    approval_callback: ApprovalCallback,
    return_permission_errors: bool = False,
) -> ToolInvocable | WorkerInvocable:
    ...
```

- **Pros**: Low risk, minimal change, makes direct Python usage shorter.
- **Cons**: Still conceptually a wrapper; does not reduce duplication.
- **When**: Immediate ergonomics without architectural changes.

**Option B: Move Wrapping into `WorkerRuntime.from_entry(...)`**

`WorkerRuntime.from_entry` accepts approval configuration and wraps internally.

```python
WorkerRuntime.from_entry(
    entry,
    model=...,
    approval_policy=ApprovalPolicy(mode="approve_all"),
)
```

- **Pros**: Removes boilerplate, centralizes approval at the "run" boundary.
- **Cons**: Runtime becomes responsible for approval; requires careful ordering.
- **When**: Clean programmatic usage without changing toolset creation.

**Option C: Move Wrapping into `build_entry(...)`**

Add approval options to `build_entry(...)` so it returns wrapped entries.

- **Pros**: Ensures every entry from loader is safe by default.
- **Cons**: Approval config is runtime-dependent; leaks UI details into loader.
- **When**: "Safe by default" entry objects that are ready to run.

**Option D: Lazy Toolset Specs**

Keep a declarative spec and instantiate wrapped toolsets only when an approval
controller is available.

- **Pros**: True "wrap at creation point", supports different modes cleanly.
- **Cons**: Larger refactor affecting discovery, entry resolution, and tests.
- **When**: Robust long-term architecture for multiple runtime modes.

**Option E: Move Approval into WorkerRuntime Directly**

WorkerRuntime becomes the sole approval gate; no wrapping layer.

- **Pros**: No wrapping at all; simpler mental model.
- **Cons**: Deep change; more coupling between runtime and toolsets.
- **When**: Eliminating `ApprovalToolset` as a dependency is acceptable.

**Option F: Add an `EntryRunner` Boundary (SOLID)**

Introduce a small “run boundary” API that owns approval wrapping, UI callbacks,
and other execution-time policy, while keeping `WorkerRuntime` focused on
dispatch/state.

```python
# llm_do/ctx_runtime/runner.py
async def run_entry(
    entry: ToolInvocable | WorkerInvocable,
    prompt: str,
    *,
    model: str | None = None,
    approval_policy: ApprovalPolicy | None = None,
    on_event: EventCallback | None = None,
    verbosity: int = 0,
    message_history: list[Any] | None = None,
) -> tuple[Any, WorkerRuntime]:
    ...
```

- **Pros**: Cleaner SRP/DIP; CLI + programmatic runs share one entry point; approval
  can remain a pluggable strategy.
- **Cons**: Adds a new public-ish API surface (but small).
- **When**: We want a single “safe execution boundary” without pushing UI/policy into `WorkerRuntime`.

### Recommended Approach for Approval (Compiler Pass)

In the compiler framing, approval wrapping is a **pass**. The key is that CLI
and programmatic runs share the *same compile pipeline*, rather than debating
whether wrapping “belongs” to the loader, runtime, or CLI.

Concrete shape (minimal churn, SOLID-friendly):

1. **Introduce an approval policy object** (execution-time inputs).
   - Fields: `approval_callback`, `return_permission_errors`, `cache`, `mode`.

2. **Introduce a single compile function** (shared by CLI and programmatic runs).
   - `compile_entry(...) -> WorkerInvocable | ToolInvocable` (optionally also returns `EntryIR` for diagnostics).
   - Internally: `load → resolve → approval plan → wrap` using shared helpers.

3. **Use a single run boundary** (Option F).
   - `run_entry(...)` becomes: `entry = compile_entry(...); ctx = WorkerRuntime.from_entry(entry, ...); return await ctx.run(...)`.
   - CLI calls `run_entry(...)` (no bespoke wrapping logic).

This keeps `WorkerRuntime` focused on execution/dispatch (SRP) and keeps approval
as a composable policy (DIP). “Move wrapping into runtime” (Option B) is still
possible, but it makes `WorkerRuntime` own policy concerns rather than treating
them as compilation/execution inputs.

---

## 4. Decisions (Locked so far)

- **Approval mechanism**: Keep `ApprovalToolset`; do not move approval into `WorkerRuntime.call_tool()`.
- **Pre-wrapped toolsets**: Not supported for now; wrapping remains an explicit compile/run-time step.
- **Approval policy**: Required for execution; disabling approvals is an explicit opt-in (e.g., `approve_all`).
- **Approval cache**: Per-run only; no persistent/shared cache.
- **Pre-approval configuration**: Use worker definition or CLI overrides, not cache persistence.
- **Run boundary**: Introduce `run_entry(...)` to decouple UI/policy from `WorkerRuntime` and share CLI/programmatic flow.
- **Wrapping location**: Keep a helper (e.g., `wrap_entry_for_approval`) and call it from `run_entry(...)` for minimal churn.
- **Context injection**: Keep full `WorkerRuntime` in `RunContext` for now; revisit a narrower `ToolContext` only if needed.

---

## 5. Open Questions

### Approval Architecture
- Wrapper pipeline: defer; treat as YAGNI unless a concrete use-case emerges.

---

## 6. Decision Factors

- **Urgency**: Option A or B for near-term ergonomics.
- **Scope tolerance**: Option D/E require non-trivial refactors.
- **API clarity**: Option B offers a clean "one entry point" for runtime config.
- **Architecture direction**: Option D is most future-proof but also most work.
