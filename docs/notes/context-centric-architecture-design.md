# Context-Centric Architecture Design

## Context
Revise the context-centric architecture to explicitly integrate the PydanticAI agent flow while keeping tools and workers unified behind a single callable protocol.

## Findings
The runtime is anchored on `ctx`, which dispatches registry entries and enforces approvals, tracing, and schema validation. Tools and workers implement the same callable protocol; the only difference is whether `call()` runs deterministic Python or a PydanticAI agent loop.

Key design points:

- **Context-first API**
  - `ctx.tools.<alias>(input)` is the primary call style.
  - `ctx.call("canonical-name", input)` remains for dynamic routing and non-identifier names.
  - `ctx.tools` is the only method namespace; context methods are reserved.

- **Unified callable protocol**
  - `name` (canonical identifier for registry lookup)
  - `schema_in`, `schema_out` (validation contracts)
  - `risk_profile` (approval and policy input)
  - `call(input, ctx) -> output` (single dispatch path)

- **Registry and naming**
  - Single registry keyed by canonical tool names; workers are registered as entries alongside tools.
  - `@tool_name("some-tool-name")` overrides the canonical name; otherwise the function name is canonical.
  - LLMs see the canonical tool name (decorator name if present, otherwise function name).

- **PydanticAI worker execution**
  - Worker entries carry configuration (prompt, model, tool allowlist, schemas, attachment policy).
  - Worker `call()` builds a PydanticAI agent using the worker config.
  - The agent registers tool wrappers derived from the registry and allowlist.
  - `ctx` is passed as agent dependencies so tool wrappers can call back into `ctx`.
  - Output verification for workers is owned by PydanticAI via `output_type` (response schema).
  - `ctx` should pass the resolved `output_model` into the agent and treat `run_result.output` as validated.
  - If output validation fails, PydanticAI raises a validation error that propagates through `ctx.call(...)`.
  - `ctx` can still apply policy checks or normalization after agent completion, but should not re-validate the schema.
  - Provider tools are worker configuration (`builtin_tools`), not registry entries.
  - They bypass `ctx` approvals and tool wrappers because execution is provider-controlled.
  - Name collisions matter at the model-facing tool schema: provider tools and registry tools share the same tool namespace passed to the LLM.

- **Tool wrappers and approvals**
  - PydanticAI tool wrappers delegate to `ctx.call(...)`.
  - Approvals, depth caps, retries, and tracing are enforced in `ctx` for every call path.
  - Output verification for code tools remains in `ctx` using `schema_out` before returning to the agent.

- **Error propagation**
  - Tool failures raise structured errors that bubble through `ctx.call(...)` to the caller.
  - Worker failures surface as agent exceptions (or failed response validation) and propagate through the same path.
  - `ctx` records failure metadata in traces and preserves the original exception for diagnostics.

- **Recursion**
  - Nested worker calls happen through the same `ctx.call(...)` dispatch.
  - Each nested worker invocation builds its own PydanticAI agent with shared approval controller and incremented depth.

Execution flow sketch:

1. Caller uses `ctx.tools.analyze(input)` or `ctx.call("analyze", input)`.
2. `ctx` resolves the canonical name in the registry.
3. If entry is a tool: validate input, enforce approval, execute deterministic call, validate output; failures bubble through `ctx.call(...)`.
4. If entry is a worker: build PydanticAI agent with tool wrappers and `ctx` deps, pass `output_model` as `output_type`, run agent, rely on PydanticAI response schema validation; failures propagate the same way.
5. Tool calls inside the agent loop flow back through `ctx.call(...)`, preserving policies, tracing, and error handling.

## Open Questions
- What is the minimal `ctx` interface required by PydanticAI tool wrappers and deps?
- How should `.worker` files map onto PydanticAI agent configuration (model, system prompt, response schema, retries)?
- What trace artifacts should be persisted: PydanticAI message logs only, or full tool call traces too?

## Conclusion
(Add when resolved) Align the registry and `ctx` API with the PydanticAI execution loop and confirm the worker configuration mapping.
