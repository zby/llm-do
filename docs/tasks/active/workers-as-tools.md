# Workers as Tools (Neuro-Symbolic Unification Phase 1)

## Goal

Unify workers and tools: a worker is just a tool whose implementation is an LLM agent loop. This is the first step toward neuro-symbolic tool unification.

See `docs/notes/neuro-symbolic-tool-unification.md` for full design.

## Background

**Current state:**
- Workers and tools are separate concepts
- Workers called via `worker_call(worker="name", input_data="...")`
- Tools are deterministic functions

**Target state:**
- Workers exposed as direct tools to the LLM (internally still uses `call_worker_async`)
- Tools can access `ToolContext` via PydanticAI's standard `ctx.deps` for nested worker calls
- Direct invocation: `code_reviewer(input="...")` instead of `worker_call`

## The Spectrum

```
Pure Tool ←————————————————————→ Agent Tool (Worker)
(all symbolic)                   (all neural)

read_file ──── smart_refactor ──── code_reviewer
   │                 │                   │
no LLM         calls LLM            full LLM
               when needed          agent loop
```

## Key Design Decisions

### ToolContext as Protocol

`ToolContext` is a Protocol that `WorkerContext` implements. This gives:
- Single runtime object (WorkerContext)
- Clean minimal interface for tools via Protocol
- Type safety - tools declare dependency on ToolContext, not full WorkerContext

```python
class ToolContext(Protocol):
    """Interface for tools needing nested agent calls."""
    depth: int
    approval_controller: ApprovalController
    cost_tracker: Optional[Any]  # Future enhancement (placeholder)

    async def call_worker(self, worker: str, input_data: Any) -> Any: ...

@dataclass
class WorkerContext:  # implements ToolContext
    # ... existing fields ...
    depth: int = 0
    cost_tracker: Optional[Any] = None  # placeholder

    async def call_worker(self, worker: str, input_data: Any) -> Any: ...
```

### Context Injection via PydanticAI

No custom mechanism needed. Use PydanticAI's standard `RunContext` dependency injection:

```python
# Tool that needs context - declares it in signature
async def orchestrator_tool(ctx: RunContext[ToolContext], task: str) -> str:
    # Delegate to a specialized worker
    result = await ctx.deps.call_worker("code_reviewer", task)
    return result

# Pure tool - no context parameter
def read_file(path: str) -> str:
    return Path(path).read_text()
```

PydanticAI automatically injects `ctx` when the tool signature asks for it.

### Depth Tracking

- `depth` field added to `WorkerContext`
- All depth logic lives in `call_worker_async` (runtime.py):
  - Check `depth < MAX_DEPTH` before execution (raise if exceeded)
  - Pass `depth + 1` when creating nested WorkerContext
- Counts only worker/agent calls (not individual tool calls)
- Configurable max (default 5)
- Enables recursion protection for nested agent calls

### Cost Tracking (Future)

Infrastructure placeholder:
- `cost_tracker: Optional[Any]` field in WorkerContext (type TBD)
- Passed through nested calls
- Actual implementation deferred to future enhancement

## Tasks

### Phase 1: ToolContext Protocol & WorkerContext Extension

Define the protocol and extend WorkerContext:

- [ ] Define `ToolContext` Protocol in `types.py` (just `call_worker` method + fields)
- [ ] Add `depth: int = 0` field to `WorkerContext`
- [ ] Add `cost_tracker: Optional[Any] = None` field (placeholder)
- [ ] Update `call_worker_async` in `runtime.py`:
  - [ ] Add `MAX_WORKER_DEPTH = 5` constant
  - [ ] Check `caller_context.depth < MAX_WORKER_DEPTH` before execution
  - [ ] Pass `depth=caller_context.depth + 1` to nested WorkerContext

### Phase 2: Implement call_worker on WorkerContext

Add the `call_worker` method to WorkerContext (implements ToolContext Protocol):

- [ ] `call_worker(worker: str, input_data: Any) -> Any`
  - Thin wrapper around `call_worker_async`
  - Depth check/increment already handled by `call_worker_async`
  - Returns just the output (unwraps `WorkerRunResult.output`)

```python
async def call_worker(self, worker: str, input_data: Any) -> Any:
    result = await call_worker_async(
        registry=self.registry,
        worker=worker,
        input_data=input_data,
        caller_context=self,  # depth handled inside
    )
    return result.output
```

**Future iteration:** Add `llm_ask` and `llm_agent` methods if needed for hybrid tools.

### Phase 3: AgentToolset (Rename DelegationToolset)

Rename and simplify:

- [ ] Rename `DelegationToolset` to `AgentToolset`
- [ ] Generate tool per allowed agent (not generic `worker_call`)
- [ ] Tool name = agent name (e.g., `summarizer` not `worker_call`)
- [ ] Tool schema from agent's definition (input as string for now)
- [ ] Remove `worker_call` indirection
- [ ] Keep `worker_create` for dynamic worker creation (if needed)

**Before:**
```
LLM sees: worker_call(worker="summarizer", input_data="...")
```

**After:**
```
LLM sees: summarizer(input="...")
```

### Phase 4: Simplify Workshop

After sandbox removal (see `15-remove-sandbox.md`):

- [ ] Remove `sandbox` from `WorkshopConfig`
- [ ] Workshop becomes directory of tool/agent definitions
- [ ] Convention over configuration

## Architecture

```
┌──────────────────────────────────────────┐
│                                          │
│   LLM ──calls──▶ Tool ──calls──▶ LLM     │
│    │               │               │     │
│    ▼               ▼               ▼     │
│  reason         execute          reason  │
│  decide         compute          decide  │
│  generate       validate         assist  │
│                                          │
└──────────────────────────────────────────┘

Context flows down: depth, approval_controller, (future: cost_tracker)
```

## Resolved Questions

1. **ToolContext vs WorkerContext**: ToolContext is a Protocol, WorkerContext implements it
2. **Context injection**: Use PydanticAI's standard `ctx.deps` mechanism
3. **Recursion limits**: Check at `call_worker_async`, depth counts worker calls only, default max 5
4. **Cost tracking**: Placeholder field, implementation deferred
5. **Iteration 1 scope**: Only `call_worker` method, not `llm_ask`/`llm_agent` (add later if needed)
6. **Attachments**: Simplify after sandbox removal — container handles file access
7. **Tool definitions unchanged**: Existing toolsets mechanism stays as-is, no new `type` field

## Dependencies

- **Prerequisite**: `15-remove-sandbox.md` should be completed first (simplifies Phase 4)

## Current State

Not started.

## References

- Design: `docs/notes/neuro-symbolic-tool-unification.md`
- Current delegation: `llm_do/delegation_toolset.py`
- Worker execution: `llm_do/runtime.py`
- Sandbox removal: `docs/tasks/active/15-remove-sandbox.md`
