# Dynamic Workers

## Idea

Enable workers to create and invoke other workers at runtime, supporting bootstrapping and iterative refinement workflows.

## Why

- Bootstrapper pattern: LLM creates specialized workers on-the-fly for tasks
- Iterative refinement: create → run → evaluate → refine loop
- Dynamic task decomposition: break complex tasks into purpose-built workers

## Required Tools

### `worker_create(name, instructions, description, model?)`
Create a new `.worker` file at runtime.
- Writes to a configured output directory (e.g., `/tmp/llm-do/generated/`)
- Returns the worker name for subsequent invocation

### `worker_call(worker, input, attachments?)`
Invoke a dynamically created worker.
- Needed because toolsets are resolved at startup, not runtime
- Alternative: dynamic re-resolution (more complex) or shell workaround

## Implementation Notes

- Previously existed as `delegation` toolset (removed)
- New toolset name: `dynamic_workers` or just `workers`
- Design note: `docs/notes/dynamic-workers-runtime-design.md`
- Consider: should created workers persist across runs or be ephemeral?
- Consider: approval requirements for worker creation

## Iterative Refinement (Future Extension)

Once dynamic workers exist, add refinement loop:
1. Create worker
2. Run with test input
3. Evaluate output (schema validation, LLM-as-judge)
4. Refine worker instructions based on feedback
5. Repeat until quality threshold met

## Why Not Now

Needs design decisions on:
- Toolset name and API
- Persistence and cleanup of generated workers
- Whether `worker_call` is needed or if dynamic resolution is feasible

## Trigger to Activate

Need for LLM-driven worker creation (bootstrapping, dynamic task decomposition).
