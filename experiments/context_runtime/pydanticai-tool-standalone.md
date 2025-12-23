# PydanticAI Tool standalone execution (draft issue)

## Problem
PydanticAI `Tool` is great for schema/validation + tool definition, but it’s tightly coupled to `RunContext`, which assumes a full agent run (real `model` + `RunUsage`). In some architectures, tools are executed outside an agent run and we only want PydanticAI’s schema/validation + a thin execution wrapper.

## Use case
We maintain a long‑lived dispatcher context that spans many workers (and their own agent runs). When tools are invoked directly (not via an Agent), we still want:
- PydanticAI tool schema generation from signatures/docstrings
- validation with `function_schema.validator`
- reuse of `ToolDefinition` metadata (`requires_approval`, `strict`, `sequential`, etc.)

But we don’t have a real `RunContext` from PydanticAI’s agent graph, nor do we want to fabricate a `model`/`usage` just to call a tool.

## Current workaround
We use both approaches in combination:

1. Fabricate a `RunContext` with our orchestration context as deps:
   ```python
   RunContext(
       deps=child_ctx,           # our Context for orchestration
       model=resolved_model,     # from Context or entry override
       usage=Usage(),            # placeholder per-model tracking
       prompt="",
       messages=[],
       run_step=depth,
       retry=0,
       tool_name=name,
   )
   ```

2. Call the function directly after validation:
   ```python
   validated = tool.function_schema.validator.validate_python(input_data)
   if tool.function_schema.takes_ctx:
       result = tool.function(run_ctx, **validated)
   else:
       result = tool.function(**validated)
   ```

This works but feels like second‑class usage. We're accessing internal APIs (`function_schema.validator`, `function_schema.takes_ctx`, `tool.function`) that aren't part of the public contract.

## Proposal (one of these would be enough)
1) Minimal/optional RunContext
   - Allow `RunContext.model` and `RunContext.usage` to be optional, or add `RunContext.stub(...)` for non‑agent use.

2) Tool execution API
   - Add something like:
     ```python
     args = tool.validate_args(payload)  # or tool.function_schema.validator
     result = await tool.execute(args, deps=deps, *, tool_name=None, tool_call_id=None)
     ```
   - `execute(...)` would construct the minimal context needed when `takes_ctx=True`, otherwise call the function directly.

3) Tool call context protocol
   - Introduce a lightweight protocol/type for tool execution that only requires `deps` and a few optional fields (`tool_name`, `tool_call_id`, `retry`), and let `Tool` accept that.

## Questions
- Is this use case in scope, or should tool execution remain exclusively within agent runs?
- Is there a reason `RunContext` must always include a full `Model` and `RunUsage`?

## Open Questions
- Which direction would maintainers prefer: relaxed `RunContext` vs dedicated `Tool` execution API vs a lightweight context protocol?
- Are there any hidden assumptions around tracing/usage collection that require a full `RunContext`?
