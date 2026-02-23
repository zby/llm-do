# Worker Call Ergonomics (A + C)

## Idea
Make worker/tool calls feel like Python function calls by accepting keyword-style inputs and providing runtime-bound callable wrappers, while keeping the runtime explicit for approvals and shared state.

## Why
The current dict-based `ctx.deps.call("name", {"input": ...})` pattern is clunky and breaks the normal function-call mental model; improving ergonomics should reduce friction without hiding approval or runtime boundaries.

## Rough Scope
- Normalize dispatcher inputs (kwargs, string -> input, BaseModel -> dict).
- Add runtime-bound callable wrapper for workers/tools.
- Update docs/examples to show function-like calls.
- Add tests for keyword-style calls and bound callables.

## Why Not Now
Feels minor relative to recent runtime refactor; needs decisions on call semantics and return shape; avoid API churn until priorities are clearer.

## Trigger to Activate
If onboarding feedback flags call ergonomics as a pain point or we are already updating runtime docs/examples and want to align narrative with function-like calls.
