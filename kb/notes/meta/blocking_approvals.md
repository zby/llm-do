---
description: Proposal for deferred_tool_handler enabling blocking approvals
---

# Deferred Handler Minimal-Core Proposal Draft

## Context
We need a minimal-core `deferred_tool_handler` proposal that preserves blocking approvals while keeping policy and UI in third-party packages. This draft should enable replacement of `pydantic-ai-blocking-approval` without expanding core beyond the loop mechanics.

## Findings
Draft proposal content:

---

# Proposal: `deferred_tool_handler` for Inline Resolution of Deferred Tools (Minimal Core)

## Summary

Add an optional `deferred_tool_handler` parameter to `Agent` and `agent.run()` that enables inline resolution of deferred tool calls (approvals and external calls) without returning control to the caller.

The core stays minimal: it only defines how deferred tool requests are surfaced to a handler and how results are applied. Approval policy, UI, caching, and "blocked" semantics remain in third-party packages.

## Goals

- Enable blocking, inline approval workflows without re-implementing the agent loop.
- Preserve current behavior when no handler is provided.
- Keep approval policy and UI in third-party packages.

## Non-Goals

- Define approval policy rules in core.
- Add new approval UI or caching APIs in core.

## Motivation

PydanticAI's current deferred tools pattern works well for batch/review workflows where tool calls are collected, reviewed externally (dashboard, email, async process), and then resumed with a new `agent.run()` call.

However, for interactive scenarios (CLI agents, coding assistants, multi-step dangerous operations), a blocking pattern is more appropriate:

1. The agent proposes tool calls
2. The user reviews and approves/denies inline
3. Approved tools execute immediately
4. The agent sees results and continues
5. Repeat until task complete

Currently, implementing this requires:
- Re-implementing the agent loop externally
- Managing message history across multiple `run()` calls
- Complex state handling for multi-agent scenarios (see #3274)

A first-class `deferred_tool_handler` makes this pattern easy while keeping approval policy out of core.

## Proposal

### API

```python
from typing import Callable, Awaitable
from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults

DeferredToolHandler = Callable[
    [RunContext[Deps], DeferredToolRequests],
    DeferredToolResults | Awaitable[DeferredToolResults]
]

# On Agent constructor
agent = Agent(
    'openai:gpt-5',
    deferred_tool_handler=my_handler,  # Optional
)

# On run methods
result = await agent.run(
    prompt,
    deferred_tool_handler=my_handler,  # Optional, overrides agent default
)
```

The handler receives `RunContext[Deps]` for consistency with other PydanticAI patterns, giving access to dependencies (database connections, config, etc.) useful for policy decisions.

### Core Behavior

When `deferred_tool_handler` is set and an LLM response contains deferred tool calls:

1. Collect all deferred tools from the response into `DeferredToolRequests`
2. Call `deferred_tool_handler(ctx, requests)` and await the result
3. Apply the returned `DeferredToolResults` to the pending tool calls
4. Execute approved tools (can be parallel)
5. Continue the agent loop with tool results
6. **Do not** return `DeferredToolRequests` to the caller (unless partial handling, see below)

When `deferred_tool_handler` is `None` (default):

- Current behavior unchanged, return `DeferredToolRequests` to caller

### What the LLM Sees

A key difference between the current offline flow and the blocking handler flow is what the LLM perceives:

**Current offline flow (no handler):**
```
LLM: "I'll delete those files" → calls delete_files(...)
                ↓
Tool raises ApprovalRequired
                ↓
LLM sees: "This action requires approval and has been saved for review"
                ↓
run() returns DeferredToolRequests to caller
                ↓
[time passes, external review happens]
                ↓
Caller resumes: run(deferred_tool_results={...approved...})
                ↓
Tool actually executes
                ↓
LLM sees: "Deleted 3 files: foo.txt, bar.txt, baz.txt"
```

**Blocking flow with handler (approved):**
```
LLM: "I'll delete those files" → calls delete_files(...)
                ↓
Tool raises ApprovalRequired
                ↓
Handler called → user approves → ToolApproved()
                ↓
Tool actually executes
                ↓
LLM sees: "Deleted 3 files: foo.txt, bar.txt, baz.txt"  ← normal result!
                ↓
Loop continues in same run()
```

**Blocking flow with handler (denied):**
```
LLM: "I'll delete those files" → calls delete_files(...)
                ↓
Handler called → user denies → ToolDenied(message="User denied: too risky")
                ↓
Tool does NOT execute
                ↓
LLM sees tool result: "Tool call denied: User denied: too risky"
                ↓
Loop continues - LLM can adapt: "I understand, let me try a safer approach..."
```

**What happens on denial:**
1. The tool function is **never called** - no side effects occur
2. A synthetic tool result is returned to the LLM containing the denial message
3. The agent loop continues with this result in the message history
4. The LLM can react to the denial (try alternative approach, ask for clarification, give up gracefully)

This matches how tool execution errors are already handled - the LLM receives an error message as the tool result and can adapt its behavior.

**Key insight:** With the blocking handler, from the LLM's perspective, deferred tools behave like normal tools—they either succeed with real results or fail with a denial message. The LLM doesn't know or care that a human was consulted in the middle. This is a cleaner mental model compared to "your request was saved for later review" which leaves things in limbo.

### Defaults and Edge Cases

- **Missing approvals in results (partial handling)**: Approval requests missing from `DeferredToolResults.approvals` are treated as **unhandled** (not denied). These unhandled requests are returned to the caller as `DeferredToolRequests`, matching the existing behavior for non-exhaustive `deferred_tool_results`. This enables hybrid flows where a handler can process some requests (e.g., auto-approve reads) while letting others bubble up to external review systems.
- **Explicit denial**: Only an explicit `ToolDenied(...)` entry means denied.
- **Handler precedence**:
  - If a handler is provided to `run()`/`run_sync()`/`run_stream()`, it overrides the `Agent` default.
  - If a handler is not provided, the `Agent` default is used.
  - To disable a handler configured on Agent for a specific run, use `agent.override(deferred_tool_handler=None)`.
  - Note: When a `deferred_tool_handler` is configured on Agent, `DeferredToolRequests` does not need to be in `output_type` (since the handler resolves them inline). Disabling the handler changes this contract, so use `agent.override()` to also adjust `output_type` if needed.

### Sync vs Async and Streaming

- `run_sync()` runs the regular `run()` in an event loop, so async handlers work fine. No special restriction needed.
- `run_stream()` should support `deferred_tool_handler` the same way as `run()`:
  1. Stream text output as usual
  2. When deferred tools appear in the response, pause streaming and call the handler
  3. After handler returns, apply results, execute approved tools
  4. Resume streaming with the next LLM response

  This mirrors how non-deferred tools are already handled in streaming—the stream pauses while tools execute.

### Granularity: Per LLM Response

The handler is called once per LLM response that contains deferred tools, not once per tool call or once for the entire run.

This design enables:

| Benefit | Explanation |
|---------|-------------|
| Full context per turn | User sees all tools the model wants to call before any execute |
| Batch decisions | "Approve all reads", "Deny all writes" |
| Parallel execution | Approved tools from same response can run concurrently |
| Blocking between turns | Model's next response waits for these results |

```
LLM Response 1 -> [Tool A, B, C] -> handler -> approve/deny -> execute -> results
LLM Response 2 -> [Tool D, E] -> handler -> approve/deny -> execute -> results
...
Final response -> output
```

## Extension Points for Approval Policies (Non-Core)

The core does not define approval policy. Third-party packages can implement policy and UI using the hook provided by `deferred_tool_handler`.

### 1) Per-Call Policy Decisions

A wrapper/toolset can decide per call whether to:

- **pre_approve** (execute immediately)
- **needs_approval** (raise `ApprovalRequired`)
- **blocked** (prevent execution without prompting)

This can be done today by raising `ApprovalRequired` or raising a policy-specific error. The `deferred_tool_handler` is the bridge that enables inline blocking without core policy logic.

### 2) Metadata Pass-Through for UI

Metadata attached to deferred tools should be preserved in `DeferredToolRequests.metadata`.

This enables third-party packages to include UI context (descriptions, policy reasons, worker name, etc.) without core types.

**Recommended (non-binding) metadata keys:**
- `approval_description`: human-readable description of the action
- `approval_reason`: why approval is needed
- `approval_policy`: e.g., "blocked" to indicate policy-blocked without prompting
- `toolset_id`, `worker`: for multi-agent UI clarity

Handlers can use these hints to decide whether to prompt the user or auto-deny.

**Design note: Supporting richer approval systems**

The metadata pass-through is intentionally flexible to support more sophisticated approval models. For example, a capability-based approval system could attach:

```python
raise ApprovalRequired(metadata={
    "required_capabilities": ["fs.write", "net.external"],
    "missing_capabilities": ["net.external"],
    "isolation_profile": "unisolated",
    "tool_name": name,
})
```

The handler then interprets these capabilities to:
- Prompt for missing capability grants
- Manage grant lifetime (per-run, inheritable to child workers)
- Apply isolation profile rules (e.g., auto-grant in isolated environments)
- Cache grants scoped to stable profiles

This keeps the core minimal (just metadata pass-through) while enabling rich policy logic in third-party packages.

### 3) Blocked vs Denied Semantics

Core does not define a new "blocked" result type. Third-party handlers may implement "blocked" by auto-returning a `ToolDenied(message="Blocked: ...")` based on metadata.

This keeps core minimal while allowing richer UX in external packages.

## Examples

### CLI with Blocking Approval (Third-Party Policy)

```python
from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolApproved,
    ToolDenied,
)

def cli_handler(ctx: RunContext[MyDeps], requests: DeferredToolRequests) -> DeferredToolResults:
    results = DeferredToolResults()
    for call in requests.approvals:
        meta = requests.metadata.get(call.tool_call_id, {})
        if meta.get("approval_policy") == "blocked":
            results.approvals[call.tool_call_id] = ToolDenied(message="Blocked by policy")
            continue

        desc = meta.get("approval_description") or f"{call.tool_name}({call.args})"
        response = input(f"Approve {desc}? [y/n]: ")
        if response.lower() == "y":
            results.approvals[call.tool_call_id] = ToolApproved()
        else:
            results.approvals[call.tool_call_id] = ToolDenied(message="User denied")
    return results

agent = Agent('openai:gpt-5', output_type=str)
result = agent.run_sync("Clean up logs", deferred_tool_handler=cli_handler)
```

### Auto-Approve for Tests

```python
def auto_approve_all(ctx: RunContext[None], requests: DeferredToolRequests) -> DeferredToolResults:
    results = DeferredToolResults()
    for call in requests.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results

result = agent.run_sync(prompt, deferred_tool_handler=auto_approve_all)
```

### Partial Handling (Hybrid Flow)

```python
def handle_reads_only(ctx: RunContext[MyDeps], requests: DeferredToolRequests) -> DeferredToolResults:
    """Auto-approve read operations, let writes bubble up to external review."""
    results = DeferredToolResults()
    for call in requests.approvals:
        if call.tool_name.startswith("read_"):
            results.approvals[call.tool_call_id] = ToolApproved()
        # Writes not added to results → unhandled → returned as DeferredToolRequests
    return results

# If any writes were requested, run() returns DeferredToolRequests for those
result = await agent.run(prompt, deferred_tool_handler=handle_reads_only)
if isinstance(result.output, DeferredToolRequests):
    # Handle remaining write approvals via external review system
    ...
```

## Implementation Notes

### Internal Loop Change

```python
# Proposed: handler resolves deferrals inline
async def run(..., deferred_tool_handler=None):
    while True:
        response = await model.call(messages)

        deferred = collect_deferred(response)
        if deferred.has_pending:
            if deferred_tool_handler:
                results = await resolve_maybe_async(deferred_tool_handler(ctx, deferred))
                apply_results(results, response)
                # Check for unhandled requests (partial handling)
                unhandled = get_unhandled(deferred, results)
                if unhandled.has_pending:
                    return DeferredToolRequests(...)  # Bubble up to caller
            else:
                return DeferredToolRequests(...)

        execute_tools(response)
        ...
```

### Compatibility

- Default `deferred_tool_handler=None` preserves current behavior.
- Existing code using `DeferredToolRequests` output type continues to work.
- No breaking changes.

## Open Questions / Gaps

- **External calls**: Deferred external calls should be in scope. The handler receives them in `DeferredToolRequests` alongside approval requests. If the handler cannot provide a result for an external call, it omits that entry from `DeferredToolResults`, and the request bubbles up to the caller as `DeferredToolRequests` (same partial handling semantics as approvals).
- **Streaming**: ~~When approvals are possible, should `run_stream()` auto-disable streaming or hard-fail?~~ **Resolved**: `run_stream()` should handle deferred tools the same way as `run()`—pause streaming, call handler, resume. This mirrors existing tool execution behavior in streams.

## Comparison with Alternatives

### External Loop Helper

An alternative is a helper function that wraps the loop externally:

```python
async def run_with_deferred(agent, prompt, handler):
    result = await agent.run(prompt)
    while isinstance(result.output, DeferredToolRequests):
        results = await handler(result.output)
        result = await agent.run(
            message_history=result.all_messages(),
            deferred_tool_results=results,
        )
    return result
```

Downsides:
- Each iteration is a separate `run()` call
- Message history management is caller's responsibility
- Streaming behavior may differ across iterations
- Doesn't compose well with other run options

### Per-Tool Handler

```python
approval_handler: Callable[[ToolCallPart], ToolApproved | ToolDenied]
```

Downsides:
- Can't show batch context ("model wants to do A, B, C")
- Can't make batch decisions ("approve all reads")
- Prevents parallel execution of approved tools
- Doesn't handle external tools pattern

## Related Issues

- [#3274](https://github.com/pydantic/pydantic-ai/issues/3274) - Human in the Loop Approval for Multi Agent Systems
- [#3488](https://github.com/pydantic/pydantic-ai/issues/3488) - Allow `user_prompt` with deferred tool approval

## Use Cases

| Use Case | Pattern |
|---------|---------|
| CLI coding assistant | Blocking approval with stdin prompts |
| IDE extension | Blocking approval with UI dialogs |
| Slack/Discord bot | Async handler awaiting user reaction |
| CI/CD pipeline | Auto-deny or auto-approve based on policy |
| Testing | Auto-approve handler |
| Web app with dashboard | Async handler with external review UI |
| Multi-agent orchestration | Handler that manages nested agent approvals |

---

## Remaining Open Questions

- Should we include a small appendix that maps `pre_approved / needs_approval / blocked` into suggested metadata conventions?
- ~~Do we need to document a fallback behavior for streaming runs when approvals are possible?~~ **Resolved**: Streaming works the same as non-streaming.
- What is the exact current behavior for non-exhaustive `deferred_tool_results`? Based on [source code analysis](https://deepwiki.com/pydantic/pydantic-ai/2.2-tools-system), missing approvals are **skipped during processing** (not automatically denied). The `_handle_deferred_tool_results` function only iterates over approvals that are present. This appears to match our proposed "missing = unhandled" semantics, but we should confirm whether unprocessed tools are returned as `DeferredToolRequests` or handled differently.

## Conclusion

This proposal enables blocking, inline approval workflows while keeping the core minimal. Key design decisions:

1. **Same types, different timing**: The handler produces `DeferredToolResults`—the same type used in the existing offline flow—but inline during the run.
2. **Transparent to LLM**: From the LLM's perspective, approved tools behave like normal tools (real results), denied tools behave like failed tools (error message). No "pending review" limbo state.
3. **Partial handling**: Handlers can process some requests and let others bubble up to the caller, enabling hybrid workflows.
4. **Consistent API**: Uses `RunContext[Deps]` like other PydanticAI patterns, works uniformly across `run()`, `run_sync()`, and `run_stream()`.


### References

