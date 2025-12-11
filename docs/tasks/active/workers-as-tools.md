# Workers as Tools

## Prerequisites
- [ ] 10-async-cli-adoption complete (async approval callbacks)

**Why dependent on async CLI?**
The current `DelegationToolset._check_approval()` uses `request_approval_sync()` which raises `TypeError` if the approval callback is async. Once we have async approval callbacks (Task 10), any new toolset must use `await controller.request_approval()` instead. Better to build workers-as-tools on the async foundation.

## Goal
Replace `worker_call` indirection with direct tool registration: each allowed worker becomes a tool the LLM can call directly.

## Background

See `docs/notes/workers-as-tools.md` for full analysis.

**Current design:**
```
LLM sees: worker_call(worker="summarizer", input_data="...")
```

**Target design:**
```
LLM sees: summarizer(input_data="...")
```

Benefits:
- More discoverable (each worker has description in tool list)
- Flatter, more natural
- LLM doesn't need to understand "delegation" concept
- Worker descriptions become tool descriptions

## Current Implementation Notes

The current `DelegationToolset` (in `llm_do/delegation_toolset.py`):
- Exposes `worker_call` and `worker_create` tools
- Uses `call_worker_async()` for execution (already async)
- Has separate `_check_approval()` for attachment approvals (uses sync API)
- Main tool approval handled by `ApprovalToolset` wrapper

Key functions in `runtime.py`:
- `call_worker_async()` - the actual delegation logic
- `create_worker()` - dynamic worker creation

## Tasks

### Phase 1: WorkerToolset Implementation
Create `llm_do/worker_toolset.py`:
- [ ] `WorkerToolset(AbstractToolset)` that generates tools from workers
- [ ] Read `workers` config (list of allowed worker names/patterns)
- [ ] Generate tool definitions from worker name + description
- [ ] `call_tool()` delegates to `call_worker_async()` (reuse existing logic)
- [ ] Handle `input_data` and `attachments` parameters
- [ ] Use `await controller.request_approval()` for any approval checks (async!)

### Phase 2: Tool Schema Generation
- [ ] Map worker definition → tool JSON schema
- [ ] Use worker `description` field as tool description
- [ ] Fall back to truncated `instructions` if no description
- [ ] Handle workers with `input_schema` (use as tool parameters)
- [ ] Handle workers with `output_schema` (for return type hints)

### Phase 3: Approval Integration
- [ ] Implement `needs_approval()` → always `needs_approval` for worker calls
- [ ] Implement `get_approval_description()` showing worker + input summary
- [ ] Handle attachment approvals with async `request_approval()`

### Phase 4: Integration with Toolset Loader
Update `llm_do/toolset_loader.py`:
- [ ] Add `worker_tools` as toolset alias
- [ ] Pass registry and worker list from config
- [ ] Wrap with ApprovalToolset like other toolsets

### Phase 5: Configuration
Support in worker definition:
```yaml
toolsets:
  worker_tools:
    workers: ["summarizer", "code-reviewer"]
    # Or use glob patterns:
    # workers: ["*"]
    # workers: ["analysis-*", "util-*"]
```

### Phase 6: Migration / Deprecation
- [ ] Deprecate `delegation` toolset (emit warning if used)
- [ ] Keep `worker_create` tool available (maybe in separate toolset?)
- [ ] Update built-in workers that reference `worker_call`
- [ ] Update examples and documentation
- [ ] Migration guide for existing configs

## Open Questions

1. **Naming conflicts**: What if worker name conflicts with another tool?
   - Option A: Prefix with `worker_` (e.g., `worker_summarizer`)
   - Option B: Error on conflict
   - Option C: Workers win, other tool gets prefixed
   - **Recommendation**: Option B (error) - explicit is better

2. **Dynamic workers** (`worker_create`):
   - Keep as separate tool? (in its own toolset)
   - Or remove entirely? (workers only from files)
   - **Recommendation**: Keep for now, separate `worker_creation` toolset

3. **Attachments**: How to expose in tool schema?
   - Option A: `attachments: list[str]` parameter on every worker tool
   - Option B: Only if worker has attachment_policy defined
   - **Recommendation**: Option B (only when relevant)

4. **Glob patterns**: Should `workers: ["*"]` expose ALL registry workers?
   - Could be dangerous (exposes workers not meant to be called)
   - Maybe require explicit listing?
   - **Recommendation**: Support globs but require at least one explicit pattern

## Architecture

```
WorkerToolset
├── __init__(config, registry)
│   └── workers: list[str]  # from config
├── get_tools(ctx) → dict[str, ToolsetTool]
│   ├── for each worker in allowed list:
│   │   ├── load WorkerDefinition from registry
│   │   ├── create ToolDefinition(name, description, schema)
│   │   └── return ToolsetTool
├── needs_approval(name, args, ctx) → ApprovalResult
│   └── return ApprovalResult.needs_approval()
├── get_approval_description(name, args, ctx) → str
│   └── "Call worker '{name}' with: {truncated_input}"
└── call_tool(name, args, ctx, tool)
    ├── validate attachments (if any)
    ├── await call_worker_async(name, input_data, ...)
    └── return result.output
```

## Current State
Not started. Waiting for 10-async-cli-adoption.

## Notes
- The `call_worker_async()` function already exists and handles the heavy lifting
- Main change is tool registration, not execution
- Consider: should we generate richer schemas from `input_schema`?
- ApprovalToolset wrapper handles the approval flow - we just implement `needs_approval()`

## References
- Design notes: `docs/notes/workers-as-tools.md`
- Current delegation: `llm_do/delegation_toolset.py`
- Worker execution: `llm_do/runtime.py` (call_worker_async)
- Toolset loader: `llm_do/toolset_loader.py`
- Approval controller: `pydantic-ai-blocking-approval/controller.py`
