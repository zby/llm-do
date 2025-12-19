# Workers as Tools

## Overview

This note explores whether workers should be exposed directly as tools to the LLM, rather than through the `worker_call` indirection.

## Current Design: Delegation via worker_call

Workers are invoked through a single `worker_call` tool:

```
LLM sees:
- worker_call(worker="summarizer", input_data="...", attachments=[...])
- worker_call(worker="code-reviewer", input_data="...")
```

**Pros:**
- Clear separation: tools are local capabilities, workers are delegations
- Single approval checkpoint for all delegations
- `allow_workers` allowlist is explicit and centralized
- Consistent interface for all worker invocations

**Cons:**
- LLM must know worker names exist (not discoverable from tool list)
- Worker capabilities aren't visible in tool descriptions
- Extra indirection: `worker_call` -> lookup -> execute
- LLM has to understand the "delegation" concept

## Alternative: Workers as Tools

Each allowed worker becomes a tool directly:

```
LLM sees:
- summarizer(input_data="...")
- code_reviewer(input_data="...")
- read_file(path="...")
- shell(command="...")
```

**Pros:**
- More discoverable - each worker has its own tool with description
- Flatter, more natural tool list
- LLM doesn't need to understand "delegation" as a concept
- Could share approval patterns with other toolsets
- Worker descriptions become tool descriptions

**Cons:**
- Blurs distinction between local tools and worker delegations
- Tool list could become very long with many workers
- How to handle `allow_workers` restrictions? (filter which become tools)
- Workers have richer semantics that don't map cleanly to tools:
  - Attachments
  - Output schemas
  - Nested context propagation
- Harder to see "this is a delegation" in logs/approvals

## Hybrid Approach

Expose workers as tools *in addition to* `worker_call`:

1. **WorkerToolset**: Auto-generates tool definitions from registered workers
2. Uses `allow_workers` to filter which workers become tools
3. Each tool's description = worker's description/instructions
4. Tool parameters mirror `worker_call`: `input_data`, `attachments`

```python
class WorkerToolset(AbstractToolset):
    """Exposes allowed workers as individual tools."""

    def __init__(self, registry: WorkerRegistry, allow_workers: list[str]):
        self.registry = registry
        self.allow_workers = allow_workers

    async def get_tools(self, ctx) -> dict[str, ToolsetTool]:
        tools = {}
        for name in self._get_allowed_workers():
            worker = self.registry.get(name)
            tools[name] = ToolsetTool(
                tool_def=ToolDefinition(
                    name=name,
                    description=worker.description or worker.instructions[:200],
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "input_data": {"description": "Input for the worker"},
                            "attachments": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                ),
                ...
            )
        return tools

    async def call_tool(self, name, tool_args, ctx, tool):
        # Delegate to worker
        return await self.delegator.call_async(
            name,
            tool_args.get("input_data"),
            tool_args.get("attachments"),
        )
```

## Configuration

```yaml
toolsets:
  delegation:
    allow_workers: ["summarizer", "code-reviewer"]
    expose_as_tools: true  # New option: expose each as separate tool
```

Or separate toolset:

```yaml
toolsets:
  worker_tools:
    workers: ["summarizer", "code-reviewer"]
    # Each becomes a tool: summarizer(...), code_reviewer(...)

  delegation:
    allow_workers: ["*"]
    # Still available via worker_call for dynamic discovery
```

## Discoverability vs Flexibility Trade-off

| Approach | Discoverability | Flexibility |
|----------|-----------------|-------------|
| `worker_call` only | Low (must know names) | High (any worker, dynamic) |
| Workers as tools only | High (in tool list) | Low (fixed at config time) |
| Hybrid | High for common workers | High for edge cases |

## Open Questions

1. **Naming conflicts**: What if a worker name conflicts with a tool name?
2. **Dynamic workers**: How to handle `worker_create`? Re-generate tool list?
3. **Approval semantics**: Per-worker approval or grouped "delegation" approval?
4. **Tool descriptions**: Use worker description, instructions, or both?
5. **Attachments UX**: How to expose attachment capability in tool schema?

## Recommendation

Start with the hybrid approach:
1. Keep `worker_call` for full flexibility and explicit delegation
2. Add optional `WorkerToolset` for discoverability of common workers
3. Let config decide which workers are exposed as tools
4. Both share the same approval flow via `ApprovalToolset`

This gives the best of both worlds without breaking existing patterns.
