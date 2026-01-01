# Approval Wrapping Architecture Options

## Context
The direct Python runner in `experiments/inv/v2_direct/run.py` recreates the CLI’s approval wrapping logic, including recursive wrapping of nested `WorkerEntry` toolsets. This is noisy for users and raises the question: can we redesign so tool approval is handled closer to tool creation, or otherwise hide the recursion behind a stable API?

This note captures the current state, why recursion exists, and multiple architectural options with concrete design sketches, tradeoffs, and implications.

## Findings
### Current state (CLI + direct runner)
- The CLI performs recursive wrapping in `llm_do/ctx_runtime/cli.py:_wrap_toolsets_with_approval`.
- The recursion exists because `WorkerEntry` is both a toolset and an owner of its own `toolsets`. Wrapping only the top-level list protects calls to a worker but not the internal tool calls inside that worker.
- The wrapper is `ApprovalToolset` from `pydantic_ai_blocking_approval`, which:
  - Calls `needs_approval()` when implemented (e.g., filesystem, shell).
  - Reads optional per-tool `_approval_config`.
  - Uses a shared `ApprovalMemory` and an approval callback (headless or TUI).
- Entry-level approval has been removed; approvals are handled only at the tool layer via `ApprovalToolset`.

### Design goals
- **Ergonomics**: avoid explicit recursive wrapping in user scripts.
- **Consistency**: match CLI semantics for approvals and error messaging.
- **Separation**: keep approval decisions centralized (headless vs TUI, approve-all vs strict).
- **Safety**: preserve default-deny semantics (unapproved tools must not run).
- **Minimal churn**: avoid large refactors unless the payoff is clear.

## Options and sketches

### Option A: Keep ApprovalToolset, but expose a public helper
**Idea**: Keep recursion, but hide it behind a small helper or higher-level runner API.

**Sketch**
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

**Pros**
- Low risk; mirrors existing CLI behavior.
- Minimal change surface; simple to document.
- Makes direct Python usage much shorter.

**Cons**
- Still conceptually a wrapper; not “at creation.”
- Does not reduce duplication if other code paths also need wrapping.

**When to choose**
- If we want immediate ergonomics without architectural changes.

---

### Option B: Move wrapping into `WorkerRuntime.from_entry(...)`
**Idea**: `WorkerRuntime.from_entry` accepts approval configuration and wraps toolsets internally.

**Sketch**
```python
WorkerRuntime.from_entry(
    entry,
    model=...,
    approval_controller=ApprovalController(mode="approve_all"),
    approval_callback=...,
    approval_memory=...,
)
```

**Pros**
- Removes approval boilerplate from almost all user code.
- Keeps toolset creation logic unchanged.
- Centralizes approval setup at the "run" boundary.

**Cons**
- `WorkerRuntime` becomes responsible for both entry-level and tool-level approval.
- Some duplication with CLI `run(...)` unless refactored.
- Requires careful ordering to avoid double-wrapping.

**When to choose**
- If we want to keep creation unchanged but make programmatic usage clean.

---

### Option C: Move wrapping into `build_entry(...)` / loader
**Idea**: Add approval options to `build_entry(...)` so it returns wrapped entries.

**Sketch**
```python
entry = await build_entry(
    worker_files, python_files, model, entry_name,
    approval_controller=ApprovalController(mode="approve_all"),
)
```

**Pros**
- Centralizes approval to the discovery/resolution stage.
- CLI `run(...)` becomes a thin call.
- Ensures every entry from loader is safe by default.

**Cons**
- Approval config is runtime-dependent (TUI vs headless), while loader is more static.
- Complicates build API; may leak UI-specific details into loader.

**When to choose**
- If we want a “safe by default” entry object that is ready to run.

---

### Option D: Lazy toolset specs (wrap at creation with controller)
**Idea**: Keep a declarative spec for toolsets and instantiate wrapped toolsets only when an approval controller is available.

**Sketch**
```python
class ToolsetSpec:
    def build(self, approval_controller, memory, callback) -> AbstractToolset:
        toolset = self.factory(self.config)
        return ApprovalToolset(inner=toolset, ...)

class WorkerEntrySpec:
    def build(self, approval_controller, ...) -> WorkerEntry:
        return WorkerEntry(..., toolsets=[spec.build(...) for spec in self.toolsets])
```

**Pros**
- True “wrap at creation point” semantics.
- Supports different approval modes without rebuilding higher-level graphs.
- Clear separation between declaration and runtime instantiation.

**Cons**
- Larger refactor: worker discovery, entry resolution, and tests change.
- Requires new spec types or changes to `WorkerEntry`.
- Riskier and more time-consuming.

**When to choose**
- If we want a robust architecture for multiple runtime modes and long-term extensibility.

---

### Option E: Move approval into WorkerRuntime (remove ApprovalToolset)
**Idea**: WorkerRuntime becomes the sole approval gate and calls `needs_approval()` directly.

**Sketch**
```python
class WorkerRuntime:
    def call_tool(...):
        if toolset_has_needs_approval:
            result = toolset.needs_approval(name, args, ctx)
            if result.needs_approval: request_approval(...)
        return toolset.call_tool(...)
```

**Pros**
- No wrapping at all; approval is fully centralized.
- Potentially simpler mental model for users.

**Cons**
- Deep change to execution path; more coupling between WorkerRuntime and toolsets.
- Must preserve all existing approval behaviors and descriptions.
- Loses separation provided by `ApprovalToolset`.

**When to choose**
- Only if we want to eliminate `ApprovalToolset` as a dependency and accept a refactor.

---

## Ergonomics comparison (CLI vs direct Python)
- CLI already hides approval wrapping and offers a short “run” surface.
- Direct Python is flexible but verbose; users are forced to recreate CLI logic.
- Options A/B offer the best “short Python” path with minimal risk.
- Options D/E are more strategic redesigns; they trade refactor cost for long-term cleanliness.

## Decision factors
- **Urgency**: If near-term ergonomics is the goal, use Option A or B.
- **Scope tolerance**: Option D/E require non-trivial refactors and test updates.
- **API clarity**: Option B offers a clean “one entry point” for runtime configuration.
- **Architecture direction**: Option D is the most future-proof but also the most work.

## Open Questions
- Do we want a single "one true" programmatic entry point (`WorkerRuntime.from_entry`) to own approval setup?
- Is approval config considered runtime-only (suggesting Option B) or part of entry construction (Option C/D)?
- Are we willing to refactor discovery/entry resolution to introduce specs and lazy build (Option D)?
- Should we keep `ApprovalToolset` as the mechanism, or is there appetite to move approval into WorkerRuntime (Option E)?
- How do we preserve CLI behavior (headless vs TUI) without duplicating logic?

## Suggested next steps
- If we want quick wins, implement Option A with a `wrap_entry_for_approval(...)` helper and use it in `experiments/` plus docs.
- If we want a clean user story, prototype Option B by adding approval parameters to `WorkerRuntime.from_entry` and moving CLI logic to a shared helper.
- If a larger refactor is acceptable, draft a spec-based loader (Option D) and identify migration path for tests and examples.
