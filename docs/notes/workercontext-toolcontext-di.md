# WorkerContext and ToolContext Dependency Injection

## Context
We need a clear reference for how runtime context flows into tools and workers,
and how custom tools opt into context injection without exposing it to the LLM.

## Findings
- `ToolContext` is a Protocol that defines the minimal interface tools can rely
  on when they need nested worker calls: `depth`, `approval_controller`,
  `cost_tracker`, and `call_worker(...)`. It lives in `llm_do/types.py`.
- `WorkerContext` is the concrete runtime context used during execution. It
  implements `ToolContext` and adds execution details such as `registry`,
  `creation_defaults`, `attachments`, and `message_callback`.
- PydanticAI uses `RunContext[WorkerContext]` for toolset execution. Toolsets
  receive a `RunContext` as `ctx` and access the injected dependency via
  `ctx.deps` (a `WorkerContext` instance).
- Custom tools in `tools.py` are normal Python functions. They only receive
  context if they opt in with `@tool_context`.
- The `@tool_context` decorator stores a marker and the parameter name (default
  `ctx`) on the function. Schema generation skips that parameter so the LLM
  never sees it.
- When a marked custom tool is invoked, `CustomToolset.call_tool` injects
  `ctx.deps` (the `WorkerContext`) into the configured parameter before calling
  the function. This is separate from PydanticAI's `RunContext` object.

Example usage in `tools.py`:

```python
from llm_do import tool_context

@tool_context
async def analyze_config(raw: str, ctx) -> str:
    return await ctx.call_worker("config_parser", raw)
```

## Open Questions
- Should `ToolContext` include `call_tool(...)` once tool/worker unification
  lands, or remain narrowly scoped to worker delegation?

## Conclusion
`WorkerContext` is the concrete dependency injected at runtime, while
`ToolContext` is the minimal protocol for tools that need delegation.
Custom tool context injection is opt-in and bypasses JSON schema exposure by
injecting `WorkerContext` directly into the tool function parameters.
