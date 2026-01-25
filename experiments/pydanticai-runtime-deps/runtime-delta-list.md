# Delta List: What’s Missing to Base llm-do on the Experiment Runtime

This document captures the gaps between the current **deps-as-runtime** experiment and
what mainline llm-do needs. It reflects two decisions from the latest discussion:

- We are willing to **re-base the UI on PydanticAI events** (no strict RuntimeEvent parity required).
- We likely want a **CallScope-like boundary** to split responsibilities and manage lifecycle.

## 1) Run-scoped state & sinks (usage + message log)
**Missing:** aggregated usage and message logs across nested calls.

**Target location:** `experiments/pydanticai-runtime-deps/runtime.py`

**Approach:**
- Introduce a shared run-scoped state object (e.g., `RunState`) held by the runtime.
- Track:
  - `usage_collector` (collect `RunUsage` from each run)
  - `message_log` and/or `message_log_callback`

**Why:** llm-do currently aggregates usage + logs across the whole run. The experiment
only propagates `ctx.usage` without a shared sink.

## 2) CallScope-like boundary (lifecycle + cleanup)
**Missing:** structured per-call lifecycle with toolset cleanup.

**Target location:** new helper (e.g., `experiments/pydanticai-runtime-deps/call_scope.py`)

**Approach:**
- Add a small `CallScope` (or `RunScope`) that:
  1) builds toolsets per call
  2) runs the agent
  3) always cleans up toolsets (`cleanup()` hooks)
- Runtime should create and enter a scope for each `agent.run(...)` call.

**Why:** per-call cleanup is required for stateful toolsets and mirrors llm-do’s existing
lifecycle boundaries. We still want to split runtime responsibilities.

## 3) Tool invocation from code (tool plane API)
**Missing:** programmatic tool invocation (for code entrypoints).

**Target location:** `experiments/pydanticai-runtime-deps/runtime.py`

**Approach:**
- Add a `call_tool(name, args, ctx)` API similar to `llm_do/runtime/context.py:CallContext.call`.
- Validate args and call the tool through the current call scope’s toolsets.

**Why:** llm-do supports a “harness layer” where code can call tools/workers uniformly.

## 4) Entry abstraction (workers vs @entry)
**Missing:** a unified entry abstraction and entry resolution logic.

**Target location:** new minimal `entry.py` (or reuse `llm_do/runtime/contracts.py`)

**Approach:**
- Define a minimal `Entry` interface or wrapper for PydanticAI agents and Python callables.
- Keep loader flexible so it can return entries that the runtime can execute in a scope.

**Why:** llm-do supports both `.worker` entries and `@entry` Python functions.

## 5) Model selection + compatibility checks
**Missing:** model compatibility logic in the experiment loader.

**Target location:** `experiments/pydanticai-runtime-deps/worker_loader.py`

**Approach:**
- Use `llm_do/models.py` to resolve model selection / compatibility.
- Respect `compatible_models` from worker frontmatter.

**Why:** this is part of llm-do’s user-facing guarantees around models.

## 6) Approval workflow integration (UI approval queues)
**Missing:** integration between approval requests and UI workflow.

**Target location:** `approval_utils.py` + runtime wiring

**Approach:**
- Provide an approval callback that can talk to the llm-do UI queue controller
  (or a new PydanticAI-first UI flow).

**Why:** approvals are still policy-sensitive; even with PydanticAI events, the UI
needs to surface approval prompts.

## 7) Runtime config surface (manifest / CLI wiring)
**Missing:** a clean runtime config structure analogous to `RuntimeConfig`.

**Target location:** new `runtime_config.py` or embed in runtime with a single dataclass.

**Approach:**
- Hold settings like `max_depth`, approval mode, verbosity, and project root.
- Construct from manifest/CLI in experiments first, then align with main.

**Why:** moving toward mainline will require consistent config wiring.

## 8) Loader convergence (shared parsing vs runtime-specific entry build)
**Missing:** clear separation between parsing + resolving and runtime-specific entry construction.

**Target location:** extract shared parsing logic (possible future refactor)

**Approach:**
- Phase A (shared): parse worker defs, resolve schema refs, resolve toolset specs
- Phase B (runtime-specific): build PydanticAI Agents + delegate tools

**Why:** reduces duplication and helps converge experiment loader with llm-do’s loader.

---

## Notes on UI + events
We decided to **re-base the UI on PydanticAI events**, which removes the requirement to
preserve `RuntimeEvent` parity. This simplifies the runtime delta: event translation
can be deferred or removed entirely.

## Notes on runtime splitting
We also expect a **CallScope-like boundary** to remain, to preserve clean lifecycle
management and keep `AgentRuntime` from growing into an untestable god object.

## Converged: Attachments
Attachments are now **converged with the main trunk**. The experiment uses:
- `Attachment` class from `llm_do.runtime.args` for lazy file references
- `render_prompt()` to resolve attachments to `BinaryContent` at call time
- `base_path` on `AgentRuntime` for relative path resolution

This replaces the previous `AttachmentResolver` class with path mapping support.
The main trunk's approach is simpler (no path aliasing) and uses lazy loading.
