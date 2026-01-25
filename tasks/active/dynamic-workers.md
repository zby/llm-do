# Dynamic Workers

## Status
ready for implementation

## Goal
Enable workers to create and invoke other workers at runtime, supporting bootstrapping and iterative refinement workflows.

## Context
- Relevant files: `llm_do/runtime/manifest.py`, `llm_do/runtime/worker_file.py`, `llm_do/runtime/registry.py`, `llm_do/runtime/context.py`
- Design note: `docs/notes/dynamic-workers-runtime-design.md`
- Previous implementation: `delegation` toolset (removed in commit 7667980)
- Example use case: `examples/pitchdeck_eval/` - orchestrator creating specialized evaluator workers

## Decision Record
- Decision: output directory configured via manifest field `generated_workers_dir`
- Rationale: manifest already handles path resolution; natural place for project config
- Decision: generated workers are NOT auto-discovered on subsequent runs
- Rationale: user should explicitly promote workers by copying to project and adding to `worker_files`; keeps human in the loop
- Decision: workers callable only within the session that created them
- Rationale: session-scoped registry avoids complexity of runtime registry mutation
- Decision: toolset name `dynamic_workers`

## Tasks
- [ ] Add `generated_workers_dir: str | None` field to `ProjectManifest`
- [ ] Create `dynamic_workers` toolset with:
  - [ ] `worker_create(name, instructions, description, model?)` - write `.worker` file
  - [ ] `worker_call(worker, input, attachments?)` - invoke created worker
- [ ] Session-scoped registry for created workers (in toolset instance)
- [ ] Parse created workers via existing `load_worker_file()` / `build_worker_definition()`
- [ ] Resolve toolsets via existing `resolve_toolset_specs()`
- [ ] Invoke via existing agent execution path
- [ ] Error if `generated_workers_dir` not configured when `worker_create` called
- [ ] Tests for create/call lifecycle
- [ ] Update/create bootstrapping example

## Implementation Notes

### Manifest Addition
```python
class ProjectManifest(BaseModel):
    # ... existing ...
    generated_workers_dir: str | None = None
```

### Toolset Structure
```python
class DynamicWorkersToolset(FunctionToolset):
    def __init__(self, generated_dir: Path, runtime: Runtime):
        self._generated_dir = generated_dir
        self._runtime = runtime
        self._created_workers: dict[str, AgentSpec] = {}  # session-scoped

    def worker_create(self, name: str, instructions: str, description: str, model: str | None = None) -> str:
        # Write .worker file to generated_dir
        # Parse and build AgentSpec
        # Register in _created_workers
        # Return name

    async def worker_call(self, worker: str, input: str, attachments: list[str] | None = None) -> str:
        # Look up in _created_workers (error if not found)
        # Call via runtime.call_agent() or equivalent
        # Return result
```

### Toolset Resolution for Created Workers
Created workers can only use toolsets already registered in the project. The `worker_create` tool should validate that any toolsets referenced in the worker spec exist.

### Approval Considerations
- `worker_create` may need approval (creates code)
- Created worker's tool calls go through normal approval flow
- `worker_call` itself probably doesn't need approval (just invocation)

## Open Questions
- Should `worker_call` also work for static workers (convenience) or only dynamic ones (strict separation)?
- What toolsets can created workers access? All project toolsets, or a restricted set?

## Verification
- Create a bootstrapping example where orchestrator creates a specialized worker
- Worker should be written to `generated/` directory
- Worker should be callable within same session
- Worker should NOT be discovered on next run without manual promotion
