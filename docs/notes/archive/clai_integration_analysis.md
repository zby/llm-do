# CLAI Integration Analysis

## Summary

We investigated basing llm-do on PydanticAI's CLAI (the `Agent.to_cli()` interface). The conclusion is that CLAI serves a different use case and would require significant modification to support llm-do's recursive worker pattern.

## What CLAI Provides

CLAI is a convenience CLI wrapper around PydanticAI agents:

- Interactive readline-based chat loop
- Special commands (`/exit`, `/markdown`, `/multiline`, `/cp`)
- Streaming response display
- Message history support
- Model selection via `"provider:model"` format

```python
agent = Agent('anthropic:claude-sonnet-4', instructions='...')
agent.to_cli_sync()  # Starts interactive loop
```

## The Core Problem: Recursive Worker Calls

llm-do's key feature is worker composition: a tool can invoke another worker which has its own tools, sandbox, and approval rules. This requires passing the runtime environment through tool calls.

The `worker_call` tool needs access to:
- `WorkerRegistry` (to load child worker definitions)
- `ApprovalController` (unified approval across nested workers)
- `Sandbox` (file boundary validation)
- `effective_model` (model inheritance chain)
- `message_callback` (streaming events from nested workers)

This is achieved via PydanticAI's `deps_type` mechanism:

```python
agent = Agent(..., deps_type=WorkerContext)
result = await agent.run(prompt, deps=context)  # Inject context
```

**Problem**: `to_cli()` doesn't accept a `deps` argument. The CLI loop creates runs internally without exposing this hook.

## Why CLAI Doesn't Fit

| CLAI Design | llm-do Design |
|-------------|---------------|
| Single agent, many turns | Many workers, hierarchical calls |
| Human in the loop each turn | Approval gates at specific tools |
| Simple tool execution | Sandboxed, validated tool execution |
| Stateless between sessions | Registry, generated workers persist |

CLAI handles the outer interactive loop but has no concept of:
- Nested agent invocations from tools
- Shared approval state across invocations
- Streaming events from child agents bubbling up
- Context inheritance (model, sandbox boundaries)

## Options Considered

### Option A: Extend CLAI to Accept deps

Modify CLAI internals to support:
```python
await agent.to_cli(deps=context, message_callback=callback)
```

**Pros**: Reuse CLAI's readline and display logic
**Cons**: Requires forking or upstreaming changes; ongoing maintenance burden

### Option B: Use CLAI for Presentation Only

Keep llm-do's runtime layer (`runtime.py`, `tools.py`, `protocols.py`) and only use CLAI for the outer CLI shell.

```
┌─────────────────────────────────────┐
│        CLAI (to_cli)                │  ← Interactive shell only
├─────────────────────────────────────┤
│    llm-do RuntimeDelegator          │  ← Worker composition
│    llm-do WorkerContext             │
├─────────────────────────────────────┤
│      PydanticAI Agent.run()         │  ← Core agent loop
└─────────────────────────────────────┘
```

**Pros**: Clean separation of concerns
**Cons**: Still need the CLAI extension from Option A; limited benefit

### Option C: Extract CLAI Features into llm-do

Port valuable CLAI features (readline integration, special commands) into `cli.py`.

**Pros**: Full control; no external dependency
**Cons**: Duplicated effort; divergence from upstream

### Option D: CLAI for Leaf Workers Only

Use CLAI for simple workers that don't delegate, use llm-do runtime for orchestrators.

**Pros**: Gradual adoption; no modifications needed
**Cons**: Inconsistent UX; two execution paths to maintain

## Recommendation

**Don't base llm-do on CLAI directly.** The runtime layer (`runtime.py`, `tools.py`, `protocols.py`) is the core value of llm-do and handles concerns CLAI wasn't designed for.

Consider:
1. Extracting useful CLAI features (readline, special commands) into `cli.py`
2. Contributing reusable components back to PydanticAI (`ApprovalToolset`, `FileSandbox`, recursive worker patterns)
3. Watching for CLAI evolution—if it gains deps support, reconsider integration

## Related

- `NESTED_WORKER_HANG_BUG.md` — Why async-by-default was essential for worker recursion
- `dependency_injection.md` — Protocol-based DI that enables recursive worker calls
