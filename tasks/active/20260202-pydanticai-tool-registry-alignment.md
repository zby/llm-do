# Align Tool/Toolset Registry With PydanticAI

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Reduce llm-do internal code **and** align with PydanticAI so developers can reuse their existing tools/toolsets unchanged, while still selecting tools and toolsets by name in llm-do.

## Context
- Relevant files/symbols:
  - `llm_do/toolsets/loader.py` (ToolsetSpec, resolve/instantiate)
  - `llm_do/runtime/registry.py` (registry merge & agent resolution)
  - `llm_do/runtime/discovery.py` (python module discovery)
  - `llm_do/runtime/agent_file.py` (YAML parsing)
  - `llm_do/runtime/context.py`, `llm_do/runtime/contracts.py` (registry interfaces)
  - `llm_do/toolsets/builtins.py` (built-in toolsets)
  - `llm_do/toolsets/agent.py` (agent-as-toolset)
  - `llm_do/toolsets/dynamic_agents.py` (toolsets passed into dynamic agents)
  - `llm_do/runtime/call.py`, `llm_do/runtime/approval.py` (approval wrapping)
  - `llm_do/runtime/agent_runner.py` (agent construction)
- Related tasks/notes/docs:
  - None. Inline decisions below.
- How to verify / reproduce:
  - Add/update focused unit tests for registry resolution.
  - Run `uv run pytest` and spot-check a simple agent YAML with tools + toolsets.
  - Ensure YAML change is limited to a `tools:` list only (no new YAML schema beyond that).

## Decision Record
- Decision: Remove `ToolsetSpec` and align registry + agent spec with PydanticAI to minimize llm-do-specific surface area and enable reuse of existing tools/toolsets.
- Inputs:
  - PydanticAI separates `tools=[...]` and `toolsets=[...]`.
  - Tools are internally stored in an agent `FunctionToolset` and combined with user toolsets.
  - Dynamic toolsets are `ToolsetFunc` callables that accept `RunContext` and may be async; default `per_run_step=True` with an option to build once per run.
  - Tool calls run concurrently by default; tools can force sequential execution via `sequential=True` or run-level sequential mode.
  - Toolset lifecycle uses `__aenter__`/`__aexit__` and is entered when the agent context is entered.
- Options:
  - Collapse everything into toolsets only (reject: reintroduces wrappers/ambiguity).
  - Keep tools + toolsets distinct with separate namespaces (accept).
- Outcome:
  - **Agent spec** includes both `tools` and `toolsets` lists.
  - **Separate namespaces**: the same name can exist in tools and toolsets; resolution is field-based.
  - **YAML stays simple**: only add a `tools:` list of names; no `per_run_step` in YAML and no other new YAML schema.
  - **Python API** can set `per_run_step`; wrap `ToolsetFunc` with PydanticAI `DynamicToolset(per_run_step=...)` when configured.
  - **Registry** stores `ToolDef = Tool | ToolFunc` and `ToolsetDef = AbstractToolset | ToolsetFunc`.
  - **Built-in toolsets** are exported as registry factories (fresh instance per agent run); runtime no longer constructs them ad hoc.
  - **Approval wrapping** stays per-run and wraps resolved toolset instances (shared or factory-produced), but must avoid stacking wrappers on shared instances. Use a non-mutating wrapper or unwrap-on-exit semantics so the underlying toolset is not repeatedly wrapped across runs.
  - **Errors**: wrong-kind resolution fails clearly at registry resolution time when the type is known (e.g., tool vs toolset). For `ToolsetFunc` factories, validate the return type **after calling** the factory (sync or async) and raise a clear error that includes the toolset name and returned type.
  - **Name collisions**: registry namespaces are separate, but tool names are merged at runtime. We will add an optional preflight check (when resolving tools/toolsets for an agent) to detect duplicate tool names early and raise a clear error that includes the originating tool/toolset names. Final enforcement still relies on PydanticAI `CombinedToolset` for safety. No ordering override; users must prefix/rename to resolve.
  - **Async factories**: supported via `ToolsetFunc` (sync or async), matching PydanticAI.
  - **Lifecycle** uses `__aenter__`/`__aexit__`. llm-do currently builds a fresh `Agent` per run and does **not** hold a long-lived agent context, so we must explicitly enter/exit the agent (or toolset) context **per run** to ensure toolset resources are set up/teardown. Shared instances will therefore be re-entered per run; if we later add long-lived agent contexts, they will enter/exit per context instead. Use toolset factories for per-run isolation and for runtime-dependent toolsets.
  - **Error surface**: wrong-kind or invalid callables fail at registry resolution time when possible; invalid factory return types fail at factory invocation time with clear messages.
  - **Tool discovery rule**: do **not** auto-register all module functions. Only explicitly exported tool entries are registered (e.g., a module-level `TOOLS` list/dict or `__all__`-limited names). Accept `Tool` instances or plain callables in that explicit registry. No automatic extraction from `Agent`-decorated tools; reusable code should export plain callables, `Tool`, or a `FunctionToolset` in the toolsets registry.
  - **Tool export precedence**: if `TOOLS` (dict or list) is defined, use it and ignore `__all__` for tools. Otherwise, if `__all__` is defined, only consider those names. Raise on duplicates, non-callables, or wrong kinds with a clear error that lists the offending names.
- Follow-ups:
  - Update docs/README to reflect tools + toolsets in agent spec once implementation is complete.
  - Scope boundary: avoid any new tool lifecycle concepts or YAML schema beyond the `tools` list.

## Tasks
- [ ] Replace `ToolsetSpec` with `ToolsetDef` types and update loader/instantiation logic.
- [ ] Add tool registry/discovery alongside toolsets; require explicit tool registries (prefer `TOOLS` list/dict; fallback to `__all__`), reject non-callables and duplicates with clear errors; accept `Tool` or plain callables for tools.
- [ ] Extend `agent_file.py` to parse `tools` list (keep YAML simple); keep toolsets list unchanged.
- [ ] Update registry resolution to enforce separate namespaces and clear error surfaces.
- [ ] Expose `per_run_step` in Python API only; wrap `ToolsetFunc` with `DynamicToolset` when configured.
- [ ] Move built-in toolset construction into registry exports as factories (fresh instance per agent run), removing runtime-only building.
- [ ] Update agent-as-toolset and dynamic agent toolset handling to use new registry types.
- [ ] Update approval wrapping and call lifecycle to operate on resolved toolsets without ToolsetSpec.
- [ ] Ensure approval wrapping does not stack on shared instances (use non-mutating wrappers or unwrap-on-exit semantics).
- [ ] Ensure agent/toolset context is entered/exited per run so toolset `__aenter__/__aexit__` runs (e.g., wrap runs with `async with agent:` in `llm_do/runtime/agent_runner.py`). Shared instances must be re-entrant across runs. Factories still use `DynamicToolset` for per-run/step entry.
- [ ] Remove/replace any `cleanup()`-based lifecycle handling; ensure toolset context entry/exit follows PydanticAI `__aenter__/__aexit__` semantics; delete now-redundant cleanup-related code paths.
- [ ] Add tests for tools + toolsets name resolution, wrong-kind errors, and built-in exposure.
- [ ] Add tests for shared-instance reuse vs factory isolation (including nested calls), toolset lifecycle entry/exit, and invalid toolset factories.
- [ ] Add tests that duplicate tool names across tools + toolsets fail fast with a clear error (CombinedToolset conflict).
- [ ] Add tests that tool discovery accepts `Tool` and plain callables, and rejects `AbstractToolset` in the tools registry (and vice versa).
- [ ] Add a preflight duplicate-name check that reports originating tool/toolset sources in the error message.

## Current State
Task created; no code changes yet.

## Notes
- Tools are not assumed stateless; concurrency is default. Use sequential flags or toolset factories for isolation.
- Keep parity with PydanticAI: tools vs toolsets are distinct inputs, but combined internally.
- Future improvement: consider a way to reuse `@agent.tool`-decorated functions in the registry without requiring new wrappers (not part of this task).
