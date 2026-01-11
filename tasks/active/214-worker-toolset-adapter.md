# WorkerToolset Adapter

## Status
ready for implementation

## Goal
Create a `WorkerToolset` adapter and switch toolset exposure to use it. This decouples
"Worker as callable entry" from "Worker as tool provider" and prepares for the
simplify-remove-registry step (removing Invocable/registry and Worker's toolset inheritance).

## Context
Design notes:
- `docs/notes/simplify-remove-registry.md` (next step)
- `docs/notes/unify-worker-tool-discovery.md` (strategy space)

Currently Worker inherits from AbstractToolset, which causes:
- Double discovery (Workers found as both toolsets and entries)
- Naming conflicts (attribute name vs worker.name)
- Conceptual confusion (Worker "is-a" Toolset vs Worker "can be exposed as" a tool)

## Decisions for simplify-remove-registry alignment
- WorkerToolset is the only way Workers are exposed as tools (no direct Worker-as-Toolset
  in toolset resolution).
- Tool name for WorkerToolset is always `worker.name` (no attribute-name aliasing).
- Add `Worker.as_toolset()` as an explicit conversion helper for Python usage.
- Move toolset approval config from Worker to WorkerToolset (Worker no longer carries
  toolset-specific approval state).
- Extract shared helper for worker tool definition/validator so we can delete `Worker.get_tools()`
  when Worker stops being a Toolset.

## Design

```python
class WorkerToolset(AbstractToolset[Any]):
    """Adapter that exposes a Worker as a single tool for another agent."""

    def __init__(self, worker: Worker) -> None:
        self._worker = worker

    async def get_tools(self, run_ctx: RunContext[Any]) -> dict[str, ToolsetTool]:
        # Return single tool with worker.name as the tool name
        # Tool schema comes from worker.schema_in (or default WorkerInput)
        # Tool description comes from worker.description
        ...

    async def call_tool(
        self,
        name: str,
        args: dict[str, Any],
        run_ctx: RunContext[Any],
        tool: ToolsetTool,
    ) -> Any:
        # Delegate to worker._call_internal() with proper context
        ...
```

Usage:
```python
analyst = load_worker("analyst.worker")
main_worker = Worker(
    name="main",
    toolsets=[analyst.as_toolset(), filesystem, shell],
    ...
)
```

## Tasks
- [ ] Add shared helper to build worker tool definition/validator
- [ ] Create `WorkerToolset` class in `llm_do/runtime/worker.py` (or new file)
- [ ] Implement `get_tools()` via the shared helper
- [ ] Implement `call_tool()` delegating to `worker._call_internal()` with proper context
- [ ] Add `Worker.as_toolset()` convenience method
- [ ] Move toolset approval config from Worker to WorkerToolset
- [ ] Update toolset resolution to inject WorkerToolset wrappers for worker references
- [ ] Update tests/examples that pass Workers directly as toolsets
- [ ] Add tests for WorkerToolset (schema, call path, approval behavior)
- [ ] Run lint/typecheck/tests

## Future Steps (not this task)
After WorkerToolset is working:
1. Remove Worker's AbstractToolset inheritance and delete `Worker.get_tools()`
2. Simplify discovery to only find Workers via worker discovery (no toolset discovery)
3. Revisit removing Invocable/InvocableRegistry per `simplify-remove-registry.md`

## Notes
- Worker-specific semantics (model selection, compatible_models) must be preserved when called via WorkerToolset
- The adapter should handle approval, events, depth tracking the same as direct worker calls
- Use explicit `worker.name` as the tool key to avoid dual naming schemes
