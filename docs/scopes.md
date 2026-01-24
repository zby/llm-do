# Scopes in llm-do

llm-do has three main scopes that govern resource lifecycle and state isolation. Understanding these scopes is essential for toolset design and runtime behavior.

## The Three Scopes

```
SESSION (Runtime)
└── ENTRY CALL (depth 0)
    ├── Turn 1 (prompt -> response)
    │   └── Call Scope (child worker, depth 1)
    ├── Turn 2 (prompt -> response)
    └── Turn 3 (prompt -> response)
```

### Session Scope

**Lifetime**: From process start to exit. One `Runtime` object per session.

**What lives here**:
- `Runtime` instance
- `RuntimeConfig` (immutable: approval mode, max depth, verbosity)
- Usage tracking (`UsageCollector`)
- Message log (`MessageAccumulator`)
- Approval callback and session-level approval cache

**When you have multiple sessions**: Each CLI invocation is a separate session. Sessions are not persisted - they exist only for the process lifetime.

**Examples**:
```bash
llm-do project.json "first prompt"   # Session 1 (one call, then exit)
llm-do project.json "second prompt"  # Session 2 (separate process)
```

### Call Scope

**Lifetime**: From entry invocation until `Runtime.run_entry()` returns. For agent toolsets, a `CallScope` is used internally to manage toolset lifecycles.

**What lives here**:
- `CallFrame` (prompt, messages, depth, active toolsets)
- Toolset instances for agent calls (created per call, cleaned up when the scope exits)
- Handle-based resources (DB transactions, browser sessions)

**Naming vs instances**: Toolsets are referenced by name in worker config (run-scoped capability), but the actual toolset instances live in the call scope. A new call gets fresh instances, even when the names are the same.

**When you have multiple calls**: Each `Runtime.run_entry()` call creates a fresh
entry call frame. Nested worker calls still create child call scopes.

```
Session (TUI with --chat)
└── Entry Calls (message_history carried forward)
    ├── Turn 1: "Analyze this file" → response
    ├── Turn 2: "Now fix the bug"   → response
    └── Turn 3: "Write tests"       → response
```

In **headless mode** or **single-turn TUI**, the entry call lasts for a single turn.

**What is a call, really?**

A call scope is the execution context for one entry invocation. It starts when
the entry is invoked and ends when `Runtime.run_entry()` returns. During a call:
1. Agent toolsets are instantiated and wrapped for approval (for agent calls)
2. One turn runs per `Runtime.run_entry()` invocation
3. Tools may create handles and state
4. Cleanup runs when the scope exits (releasing handles, closing connections)

The key property: **all state created during a call is cleaned up immediately after that call**. This ensures that:
- Uncommitted DB transactions are rolled back
- Browser sessions are closed
- File handles are released
- The next call starts fresh

### Turn Scope

**Lifetime**: One prompt -> response within a call scope.

Turns update the `CallFrame` prompt and, for the top-level agent (depth 0),
append to message history. Nested worker calls always start with fresh history.

## Scope Summary

| Scope | Lifetime | Created When | Cleaned Up When |
|-------|----------|--------------|-----------------|
| Session | Process lifetime | CLI/TUI starts | Process exits |
| Call | One entry invocation | `Runtime.run_entry()` | Call returns |
| Turn | One prompt→response | `CallScope.call_tool("main", ...)` called | Response returned |

## Implications for Toolset Design

When designing toolsets, consider which scope your state belongs to:

**Session-scoped** (rare):
- Truly stateless configuration
- Examples: shell command rules, static file paths

**Call-scoped** (most common):
- State that must be isolated between invocations
- Examples: DB transactions, browser sessions, file handles, per-call caches
- Use the handle pattern for explicit state management
- Must implement `cleanup()` to release forgotten handles at call end

**Turn-scoped** (rare):
- Ephemeral data tied to a single prompt
- Examples: per-turn metrics, temporary buffers

## The Chat Mode Exception

Chat mode (`--chat`) keeps message history across turns by passing `message_history`
back into `Runtime.run_entry()`. This enables:
- Message history continuity across turns (depth 0 only)
- Session-level approval caching (approve once, remember for session)

Toolsets and handles still follow per-call lifetimes for agent executions.

## See Also

- [architecture.md](architecture.md) - Runtime and CallScope details
- [Task per-call-toolset-instances](../tasks/active/per-call-toolset-instances.md) - Per-call toolset instances implementation
