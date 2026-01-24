# CallSite vs CallScope (Tool Lifecycle)

## Context
We are simplifying the runtime surface. Entry functions should not call tools directly; the normal path is a single agent owning chat. Tool invocation was removed from `WorkerRuntime`, and `CallScope.call_tool` is now unnecessary. We still expect to revisit call/turn boundaries once multi-agent chat returns.

## Findings
- **Current shape:** `CallFrame` holds per-call state, `WorkerRuntime` owns the call boundary (`call_agent` + depth), and `CallScope` is now just a lifecycle wrapper that closes toolsets.
- **Tool invocation:** For now, tools are invoked only through agent runs (PydanticAI). Direct tool calls from entry code are intentionally unsupported.
- **CallSite idea:** If we later move toolset instantiation + approval out of `WorkerRuntime`, a “CallSite” can act as the factory that creates `CallFrame` + `CallScope` and returns a ready-to-run child runtime.

## Open Questions
- Should CallSite live as a helper function, or be owned by `Runtime` as the canonical call boundary?
- When multi-agent chat returns, should `CallScope` regain a tool-invocation surface, or should tool calls remain agent-only?
- Where should approval wrapping live in the long term: `WorkerRuntime.call_agent` or a CallSite builder?

## Conclusion
Deferred. We removed direct tool invocation and will revisit CallSite/CallScope responsibilities when multi-agent chat becomes a priority.
