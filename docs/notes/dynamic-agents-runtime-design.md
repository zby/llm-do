# Dynamic Workers Runtime Design

Design note for runtime creation and invocation of workers (`worker_create` /
`worker_call`).

Related:
- `tasks/active/dynamic-workers.md` (implementation tracking - has more current decisions)
- `docs/architecture.md` (run boundary + ApprovalPolicy)

**Note (2026-01):** The active task has resolved many open questions from this design note. Key decisions:
- Toolset name: `dynamic_agents` (using "agents" terminology)
- Tool names: `agent_create`, `agent_call`
- Output directory: configured via manifest `generated_agents_dir`
- Created agents are session-scoped, NOT auto-discovered on subsequent runs
- Adding tools mid-session is acceptable; removing is not

---

## 1. Current State

Dynamic workers are **not implemented**:

- Workers are resolved at `build_entry_registry()` time before any worker runs.
- An LLM cannot create and invoke a new worker during execution.
- Previously existed as `delegation` toolset with `worker_create`/`worker_call`
  tools, but this was removed.

## 2. Requirements

**Problem**: Cannot create workers at runtime for bootstrapping or dynamic task
decomposition.

**Use Cases**:
- **Bootstrapping**: LLM creates specialized workers on-the-fly for novel tasks
- **Iterative refinement**: create → run → evaluate → refine loop
- **Dynamic decomposition**: break complex tasks into purpose-built workers

**Required Capabilities**:
1. **`worker_create(name, instructions, ...)`** - Write a `.agent` file at runtime
2. **`worker_call(worker, input, ...)`** - Invoke a dynamically created worker

`worker_call` is needed because `ctx.deps.call(name, input)` only works for
workers resolved at startup. Alternatives:
- Dynamic re-resolution (complex, may have side effects)
- Shell workaround: `llm-do new.agent "input"` (works but hacky)
- PydanticAI `DynamicToolset` exposure (works for *next run step*, but not
  create+call in the same model response due to per-step tool definition caching)

## 3. Proposed Design

A new toolset (e.g., `dynamic_workers`) providing:

- `worker_create(name, instructions, description, model?)` - creates `.agent` file
- `worker_call(worker, input, attachments?)` - invokes the created worker

### Experimental scope (YAGNI)

Dynamic workers should remain **experimental** for a long time. The goal is to
enable fast iteration on bootstrapping/decomposition workflows, not to design a
fully-general plugin/runtime system up front.

**Non-goals (for now)**:
- Stable long-lived public APIs beyond `worker_create`/`worker_call`
- Cross-run persistence semantics (beyond “write a file so humans can inspect/copy it”)
- Over-abstracted resolver/store layers (only introduce interfaces once we have ≥2 real implementations)

**Start small**:
- Keep a simple in-memory session registry of created workers
- Default to a temp output directory that can be configured
- Reuse existing loader/approval helpers where possible; avoid new “framework” layers

### Keep “workers are tools”, but don’t fight PydanticAI’s tool lifecycle

We should keep using PydanticAI’s tool registry (toolsets → tool defs per run
step) and use a small session registry only as backing state for dynamic
workers.

Key constraint: PydanticAI caches tool definitions per run step. A worker that
didn’t exist when the model generated its response cannot be called “by name”
in that same response. This makes `worker_call` a core UX tool, not optional.

### Proposed shape

- **Session registry** (runtime-owned state): stores session-created `Worker`s
  and any metadata needed for persistence (path, created_by, etc.).
- **`dynamic_workers` toolset**: exposes:
  - `worker_create(...)`: validate name, write `.agent`, load/build `Worker`,
    wrap its toolsets for approval, then register it in session registry.
  - `worker_call(worker=..., input=..., attachments=...)`: resolve worker from
    session registry and run it immediately.
- **Optional**: expose created workers as normal tools on subsequent run steps
  using `pydantic_ai.toolsets.DynamicToolset(per_run_step=True)` that returns a
  toolset composed from session registry contents.

Note: The current architecture uses `EntryRegistry` for static worker resolution.
Dynamic workers would need a separate session-scoped registry.

### Ordering and correctness details

- `worker_create` and `worker_call` should have `ToolDefinition.sequential=True`
  so if the model emits both in one response, they execute in order.
- `worker_create` must **validate** and **not rename** `name` silently; the model
  will use that name immediately in `worker_call`.
- Consider restricting `worker_call` to **session-generated** workers only (safer
  mental model: configured workers are called directly by name; `worker_call` is
  the "dynamic escape hatch").

### Interaction with Approval

- `worker_create` itself may need approval (creating executable code)
- Tools within the created worker need approval wrapping
- `worker_call` must run a worker only after the worker’s toolsets are wrapped

The easiest way to keep CLI vs programmatic behavior consistent is to route
dynamic-worker compilation/wrapping through the same approval boundary described in
`docs/architecture.md`.

## 4. Open Questions

- Should created workers persist across runs or be ephemeral?
- Where should generated workers be stored? (configurable output directory)
- Should `worker_call` build a fresh `CallContext` or reuse the parent's config?
- Do we also expose created workers as normal tools on later steps (DynamicToolset),
  while keeping `worker_call` for create+call-in-one-response?
- Do we restrict `worker_call` to session-generated workers only?
