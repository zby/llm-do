---
description: What llm-do adds on top of vanilla PydanticAI agents
areas: [pydanticai-upstream-index]
---

# llm-do vs vanilla PydanticAI: what the runtime adds

## Context
We need to document (for README and other docs) what llm-do adds on top of plain
PydanticAI agents, especially around multi-agent delegation and dependencies.
The PydanticAI docs show agent delegation by calling another agent inside a tool,
but llm-do introduces a runtime/harness and more structure. The question is:
what changes in the computational model vs. what is just packaging/convenience?

## Findings

### Baseline: PydanticAI multi-agent patterns
- PydanticAI supports "agent delegation": one agent calls another inside a tool
  and then resumes control. The delegate run typically receives dependencies
  from the parent.
- Delegation is explicit: you create multiple `Agent` objects and call
  `other_agent.run(...)` inside a tool.
- Agents are stateless and designed to be global; you typically pass dependencies
  rather than re-instantiating agents inside tools.
- Each agent has its own tool list and dependency type. Cross-agent calls require
  you to pass `deps` manually (or construct them) to keep things consistent.
- Delegate agent dependencies should be the same as (or a subset of) the parent
  dependencies; otherwise you must build a new deps object inside the tool.
- PydanticAI itself offers multiple coordination styles (single agent, delegation,
  programmatic hand-off, graphs, deep agents). You choose the style and wire it
  in application code.

### What llm-do adds (concrete behavior)
- A **runtime registry** that resolves agents and tools/toolsets by name, with
  `.agent` files and `TOOLS`/`TOOLSETS` registries loaded from a project manifest.
- A **unified tool/agent namespace**: agents are exposed as tools and live in
  the same global registry as toolsets, but each agent declares a *subset* of
  toolsets to include. The LLM only sees a per-agent tool list.
- **Entry functions**: deterministic orchestration in Python (no tools, no LLM),
  which can call agents via a `CallContext`.
- **Toolset lifecycle management**: toolsets are instantiated per call, cleaned
  up automatically, and isolated from each other.
- **Approvals as a first-class policy**: all tool calls can be wrapped with
  blocking approval checks, defined globally at the run boundary. llm-do wires
  in `pydantic-ai-blocking-approval` and exposes simple rule configuration.
- **CLI/TUI harness**: tool approvals, event streams, and run controls are
  integrated for interactive use (not just library calls).

### What changes in the computational model (vs plain PydanticAI)

1) **Name-based dispatch with a global registry + per-agent action space**
   - In vanilla PydanticAI, delegation is a direct object call
     (`other_agent.run(...)`) inside a tool. The action space for an agent is the
     tools you attach to it.
   - In llm-do, names live in a **shared registry** (tools + agents-as-tools),
     but each agent selects which toolsets to include via frontmatter. The LLM
     only sees that per-agent tool list; PydanticAI dispatches tool calls by
     name within it. This keeps the call site **implementation-agnostic** and
     enables late binding without bloating context.
   - Computationally, this is a shift from *"direct reference"* to *"string-named
     dispatch"* as the core abstraction, which makes refactoring across the
     neural/symbolic boundary a first-class operation.

2) **A runtime/harness boundary with interception points**
   - Tool calls are treated as syscalls: the runtime can intercept, approve,
     reject, or log them. This changes the semantics of a tool call (it can
     block or be denied).
   - Even though the blocking logic lives in `pydantic-ai-blocking-approval`,
     llm-do makes *global* policy resolution the default, not an opt-in pattern.

3) **Explicit call scopes and lifecycle management**
   - llm-do formalizes per-call state (prompt/messages, active toolsets) and
     per-runtime state (agent registry, approval policy/callback).
   - Child agent calls get a fresh call scope; toolsets are not inherited. This
     makes isolation the default and prevents accidental state leakage.

4) **Deterministic orchestration as a first-class entry**
   - Entry functions run under a NullModel (no tools, no LLM), making the
     deterministic/stochastic boundary explicit and intentional.

### Messaging emphasis (pragmatic vs conceptual)
- **Pragmatic emphasis:** the unified tool/agent namespace is the clearest,
  most stable differentiator to lead with. Approvals are important but still
  evolving, so we should not anchor the positioning on them.
- **Conceptual umbrella:** the broader message remains the hybrid VM framing:
  a single call surface where neural and symbolic components can swap without
  changing call sites.

### Comparison: subagents-pydantic-ai (vstorm-co)
Subagents is a focused delegation toolset for PydanticAI. It adds a `task`
tool (plus `check_task`, `answer_subagent`, cancellation, etc.) that lets a
single parent agent spawn named subagents. It supports sync/async/auto execution
modes, nested subagents, dynamic agent creation, and a pluggable message bus.

Key contrasts with llm-do:
- **Call surface:** subagents exposes delegation via a *single tool* (`task`)
  that accepts `subagent_type`. llm-do exposes agents and tools as *peers* in a
  shared namespace, so the LLM calls the target by name directly.
- **Async task lifecycle:** subagents provides background task management,
  status checks, and question/answer flows. llm-do does not provide a built-in
  task manager or message bus abstraction.
- **Runtime registry vs toolset add-on:** subagents is a toolset you attach to
  an existing agent. llm-do provides a registry, entry orchestration, and call
  scopes as first-class runtime concepts.
- **Dynamic agent creation:** subagents supports on-the-fly agent creation with
  a registry and limits. llm-do currently centers on declarative agent specs
  loaded at startup.

When subagents-pydantic-ai is likely enough:
- You already have a single PydanticAI parent agent and want a simple way to
  delegate tasks (including async/background work) without adopting a runtime.
- You need message-bus style coordination or distributed subagent execution.

When llm-do is still the better fit:
- You want the **unified tool/agent namespace** so you can swap agents and tools
  without changing call sites (hybrid VM story).
- You want deterministic Python entry orchestration and per-call isolation as
  first-class runtime behavior.

Overlap:
- Both enable delegation and hierarchical agent structures.
- Both rely on PydanticAI under the hood and keep tool usage explicit.

### Potentially adoptable ideas from subagents
- **Async task lifecycle API**: `task/check_task` with explicit states and
  cancellation could map cleanly onto a future llm-do task manager (if we want
  background work without forcing a message bus).
- **Parent/child question flow**: a structured question/answer channel for
  blocked subagents could become a runtime-level primitive.
- **Message bus abstraction**: a pluggable bus enables distributed execution,
  though it introduces complexity and may conflict with llm-do’s “local runtime”
  framing.
- **Dynamic agent creation**: runtime agent factories with limits and allowed
  models could be valuable for bootstrapping, but should respect the unified
  namespace and approval boundaries.
- **Auto-mode heuristics**: simple heuristics for sync vs async could be reused
  if llm-do ever exposes background execution.

### What is *not* fundamentally new
- llm-do does not change the underlying LLM semantics. It still uses PydanticAI
  Agents and toolsets under the hood.
- Most features (delegation, dependency passing, approvals) can be reproduced
  manually in PydanticAI with additional glue code.
- The blocking approval mechanism itself is not unique to llm-do; the main value
  is centralized policy wiring and consistent run-level defaults.

### When vanilla PydanticAI is enough
- Single-agent or small multi-agent apps where wiring explicit `Agent` objects
  is easy and you do not need a shared registry.
- You are comfortable passing `deps` manually and managing tool lists.
- You prefer graph/state-machine orchestration (Pydantic Graph) or already have
  your own runtime/harness layer.
- You do not need file/shell tools with human approval gating.

### When llm-do is the better fit
- You want **safe, interactive tool execution** (file/shell ops) with approvals,
  and a CLI/TUI that handles prompting, caching, and logging.
- You want **uniform composition** where agents and tools are interchangeable,
  enabling progressive stabilization from LLM to code without prompt rewrites.
- You want **project-level structure**: `.agent` specs, manifest loading,
  standardized toolsets, and centralized runtime configuration.
- You need **consistent isolation** between agent calls and tool instances,
  including max-depth enforcement and cleanup.
- You want deterministic entry points that still orchestrate agents, without
  introducing a graph DSL.

### Tradeoffs / costs of llm-do
- More structure than a simple `Agent.run()` call: manifests, runtime config,
  toolset factories, and registry wiring.
- Slightly higher conceptual overhead: you adopt the runtime/harness model even
  for small tasks.
- If you only need one or two agents, llm-do can feel like extra machinery.

## Open Questions
- In docs, how strongly should we frame the **unified tool/agent namespace** as
  the primary computational-model change vs. approvals as the main user-visible
  difference?
- Should we position llm-do as a *default harness* for PydanticAI, or as a
  specialized runtime for certain classes of projects?
- Do we need a minimal side-by-side example that shows the *minimum* amount of
  glue code saved by llm-do for delegation + approvals?

## Conclusion
(Draft) The fundamental addition is not a new LLM capability but a **runtime
model**: name-based dispatch, explicit call scopes, and a harness that mediates
all tool calls. This changes the computational model from "explicit object
wiring" to "late-bound names with interception". For small apps, vanilla
PydanticAI is enough; llm-do becomes valuable when you need safe tool execution,
uniform composition, and a stable refactor path between LLM agents and code.
For outward messaging, lead with the unified tool/agent namespace; keep
approvals secondary until that surface is more mature, while framing everything
under the hybrid VM umbrella.

---

Relevant Notes:
- [approvals-guard-against-llm-mistakes-not-active-attacks](./approvals-guard-against-llm-mistakes-not-active-attacks.md) — grounds: the "syscall interception" framing treats tool call mediation as a UX feature (visibility and error-catching), consistent with approvals being a UI mechanism rather than a security boundary
- [capability-based-approvals](./capability-based-approvals.md) — extends: the runtime interception points are where capability declarations get evaluated against session policy — the "syscall" model IS capability-based approval
- [toolset-state-prevents-treating-pydanticai-agents-as-global](./toolset-state-prevents-treating-pydanticai-agents-as-global.md) — details why llm-do constructs Agents per-call instead of reusing them as PydanticAI docs recommend

Topics:
- [index](./index.md)
- [pydanticai-upstream-index](./pydanticai-upstream-index.md)

## References
- https://ai.pydantic.dev/multi-agent-applications/#agent-delegation-and-dependencies
- https://github.com/vstorm-co/subagents-pydantic-ai
- subagents-pydantic-ai/README.md
- subagents-pydantic-ai/docs/index.md

Topics:
- [pydanticai-upstream-index](./pydanticai-upstream-index.md)
