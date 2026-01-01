# Context Injection for Tools (ctx_runtime)

## Context
We need a clear reference for how runtime context flows into tools and workers
in the ctx_runtime design, and how tools access it without exposing it to the
LLM schema.

## Findings
- The runtime context is `llm_do.ctx_runtime.WorkerRuntime`.
- Tools receive a `RunContext[WorkerRuntime]` from pydantic-ai. The runtime is
  available as `ctx.deps`.
- Tool schemas are derived from the non-`RunContext` parameters, so the LLM
  never sees the runtime context parameter.
- Nested tool/worker calls use `ctx.deps.call(name, input)`.
- There is no separate `@tool_context` decorator; context access is opt-in by
  accepting `RunContext[WorkerRuntime]` as the first parameter.

Example usage in `tools.py`:

```python
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from llm_do.ctx_runtime import WorkerRuntime

tools = FunctionToolset()

@tools.tool
async def analyze_config(ctx: RunContext[WorkerRuntime], raw: str) -> str:
    return await ctx.deps.call("config_parser", {"input": raw})
```

## Open Questions
- Do we want a small Protocol ("ToolContext") to type the minimal surface
  (for example, just `call(...)`) instead of exposing the full `WorkerRuntime`?

## Conclusion
Context injection is handled by pydantic-ai via `RunContext[WorkerRuntime]`. Tools opt
in by accepting the `RunContext` parameter, and use `ctx.deps` for nested calls
without exposing runtime details to the model schema.
