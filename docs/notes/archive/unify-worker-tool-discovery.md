# Unify Worker/Toolset Discovery

## Context
We want tools and workers to feel unified, but the runtime currently discovers
Workers twice (as toolsets and as workers) and uses two naming schemes
(module attribute names for toolsets vs `worker.name` for entries). This note
captures the strategy space and trade-offs before changing the discovery
pipeline.

## Findings
Current behavior:
- `discover_toolsets_from_module()` returns any `AbstractToolset`, including `Worker`.
- `discover_workers_from_module()` returns `Worker` instances keyed by `worker.name`.
- Registry building uses toolset attribute names for toolset lookup but uses
  `worker.name` for entry lookup.
- `_get_tool_names()` special-cases `Worker` and uses `worker.name`.

Resulting inconsistencies:
- A Python `Worker` can be referenced by attribute name in toolset lists, but
  appears as an entry under `worker.name`.
- Workers are effectively discovered twice and then deduped by ad-hoc rules.

Constraints to preserve:
- Worker entries need Worker-specific semantics (model resolution,
  compatible_models, schema_in). Treating a Worker as a generic tool
  (`ToolInvocable`) changes behavior.
- Toolsets can expose multiple tools; some toolsets require runtime context to
  enumerate tools, so entry exposure cannot always be derived from toolsets.

## Relationship between Invocables, ToolInvocable, Worker, and Toolset
Key roles:
- Invocable: runtime entry contract (`name` + `call(...)`).
- Toolset (AbstractToolset): provider of tools for the agent.
- Worker: both an Invocable and a Toolset (so it can be an entry and also be
  called as a tool by other workers).
- ToolInvocable: adapter that wraps a single tool from a toolset and exposes it
  as an Invocable entry.

Why this matters:
- Entry execution (Invocable) uses worker-level semantics like model selection
  and `compatible_models`. Tool execution does not.
- Treating a Worker as a generic tool (ToolInvocable) changes those semantics.
- The current double-discovery happens because Worker is both an Invocable and
  a Toolset, and discovery uses different naming schemes for each path.

Why Worker is a Toolset:
- The base primitive is a tool, but PydanticAI groups tools into toolsets so
  related tools can be added in one sweep (filesystem, shell, etc.).
- The runtime config today is "add toolsets to an Agent", so making Worker a
  Toolset is a packaging decision that lets you add a Worker to another Worker
  with the same API.
- This is not a fundamental requirement. If we had a "add tools" surface (or a
  higher-level "add providers" surface), Workers could stay as pure Invocables
  and be adapted at the boundary.
- The confusion comes from this packaging choice leaking into discovery and
  naming rules, not from the idea of worker delegation itself.

## How an LLM tool call happens (runtime view)
High-level flow when a Worker runs and the model calls a tool:
1) The Worker builds a PydanticAI `Agent` with a list of toolsets.
2) Each toolset exposes tools via `get_tools(...)`; PydanticAI flattens these
   into one tool-name → ToolsetTool map.
3) The model emits a tool call with a `name` and `args`.
4) The Agent’s tool manager looks up the name in the combined map and routes
   execution to the owning toolset’s `call_tool(...)`.
5) Approval wrappers (if present) can block or prompt before execution.
6) The tool returns a result, which is added to the message history; runtime
   emits ToolCall/ToolResult events and updates message history.

## Strategy Space (expanded)

### Trade-off axes
- Naming: attribute name vs `worker.name` vs explicit registry key.
- Discovery: one pass vs two passes, and where to dedupe.
- Representation: Worker as Toolset vs Worker adapter Toolset.
- Entry exposure: tools as entries vs workers as entries vs both.

### Strategy 0: Keep status quo, document clearly
Do nothing to discovery; add documentation clarifying the two naming schemes
and the fact that Python Workers can be referenced by attribute name in toolset
lists but by `worker.name` as entries.

Pros:
- No behavior changes.
- Zero migration cost.

Cons:
- Inconsistency remains and is easy to trip over.
- Still two discovery passes and ad-hoc dedupe.

### Strategy 1: Keep separate discovery, unify naming (worker.name everywhere)
Exclude `Worker` instances from toolset discovery. Inject `python_workers` into
`available_toolsets` keyed by `worker.name`. Remove the `Worker` branch from
`_get_tool_names()`.

Pros:
- One naming scheme for workers (`worker.name`).
- Minimal code changes, preserves Worker entry semantics.

Cons:
- Drops the attribute-name alias for Python Workers in toolset lists.

### Strategy 2: Keep separate discovery, unify naming (attribute name everywhere)
Force workers to be referenced by their module attribute name, treating that as
the canonical key for toolsets and entries.

Pros:
- Aligns Python discovery with toolset naming without new APIs.

Cons:
- Breaks `.worker` files and `worker.name` as the public identifier.
- Entry names would no longer be stable across modules/refactors.
- Mismatched with docs and intended mental model.

### Strategy 3: Introduce explicit aliasing
Register workers under both names: `worker.name` and module attribute name, or
support an explicit alias map in registry construction.

Pros:
- Preserves compatibility with both naming schemes.
- Can smooth migration if changing defaults.

Cons:
- Ambiguous lookups and duplicate entry errors become harder to reason about.
- Harder to make "single source of truth" guarantees.

### Strategy 4: Add a registry_name hook for toolsets
Allow toolsets to define an optional `registry_name` (or similar) attribute used
for toolset lookup. Default to module attribute name if not provided.

Pros:
- Explicit naming control without hard-coding attribute names.
- Lets you standardize naming across built-ins, Python toolsets, and workers.

Cons:
- New convention to document and enforce.
- Does not itself solve Worker double-discovery unless combined with Strategy 1/2.

### Strategy 5: WorkerToolset adapter (Worker is no longer a Toolset)
Remove `Worker` inheritance from `AbstractToolset`. Instead, create a wrapper
Toolset (e.g., `WorkerToolset`) when a Worker is used as a tool in another
worker's toolset list.

Pros:
- Clean separation: Worker is only Invocable.
- Discovery becomes unambiguous; toolset discovery never sees Workers.

Cons:
- Larger refactor. Adapter must preserve behavior, approvals, events, etc.
- `.toolsets` on a Worker would now hold toolsets and wrappers, not Workers.

### Strategy 6: Provider protocol (entries + toolsets in one interface)
Define a local protocol that yields entries and toolsets. A module scan produces
providers instead of raw objects. Workers provide entries only; toolsets provide
Toolsets and optionally entry wrappers if tools can be enumerated.

Pros:
- Single discovery pipeline, no special-casing.
- Makes "what is an entry" vs "what is a toolset" explicit.

Cons:
- More structural change. Toolsets that need run context still cannot expose
  entries at discovery time.

### Strategy 7: Tools-first API surface
Move runtime configuration to accept tools directly, with toolsets as optional
helpers that expand into tools. Workers could become tools (or tool providers)
without needing to be toolsets.

Pros:
- Matches the "tool is the primitive" mental model.
- Would likely eliminate the Worker-as-Toolset confusion entirely.

Cons:
- Largest change; would require refactoring integration with PydanticAI Agent,
  which expects toolsets.
- Risk of breaking existing configs and tooling.

### Strategy 8: Entry/toolset alias table at registry level
Keep discovery as-is but build a separate alias table that maps toolset names
and worker names into a unified lookup, with explicit conflict rules.

Pros:
- Centralizes naming resolution without changing discovery.
- Can enforce consistent conflict handling.

Cons:
- Adds indirection and still keeps double discovery.

## Proposed Refactor: WorkerToolset adapter (Strategy 5)
Summary of the approach we want to try next:
- Make `Worker` a pure Invocable (no longer an `AbstractToolset`).
- Add a `WorkerToolset` adapter that wraps a Worker and exposes it as a single
  tool (keyed by `worker.name`) for other workers to call.
- Use these adapters in toolset resolution instead of passing Worker directly.

Why it is clean:
- Eliminates double discovery and dual naming for Python Workers.
- Preserves Worker entry semantics (model selection, `compatible_models`,
  schema_in) while still allowing worker delegation via tools.

Expected code impacts:
- Discovery: Workers are no longer seen as toolsets; discovery focuses on
  actual toolsets + explicit worker discovery.
- Registry/toolset resolution: build `WorkerToolset(worker)` adapters and
  inject them into `available_toolsets` keyed by `worker.name`.
- Tests: places that currently pass a Worker as a toolset (e.g., `toolsets=[sub_worker]`)
  should pass `sub_worker.as_toolset()` or `WorkerToolset(sub_worker)` instead.

Decisions to lock in:
- Ergonomics: add `Worker.as_toolset()` as the explicit conversion helper?
- Naming: drop attribute-name aliases for Python Workers and use `worker.name` everywhere?
- Approval config: move toolset approval config to the adapter (Worker no longer
  carries toolset approval state).
- Placement: define `WorkerToolset` in `runtime/worker.py` for shared helpers,
  or in a dedicated module for separation.

## Open Questions
- Which axis are we optimizing for: minimal change, unified naming, or a
  cleaner conceptual model (tools-first or provider-first)?
- Are we willing to break attribute-name aliases for Python Workers?
- Do we want a single discovery pass that separates workers/toolsets, or is
  it enough to keep two passes but make naming consistent?
- If we introduce a registry-name hook, should it be optional (fallback to
  attribute name) or required to avoid implicit naming?

## Conclusion
(No decision yet.)
