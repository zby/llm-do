# Scopes in llm-do

llm-do has three main scopes that govern resource lifecycle and state isolation. Understanding these scopes is essential for toolset design and runtime behavior.

## The Three Scopes

```
┌─────────────────────────────────────────────────────────────────┐
│  SESSION                                                         │
│  (Runtime object lifetime - one CLI/TUI invocation)             │
│                                                                  │
│  ┌────────────────────────┐  ┌────────────────────────┐         │
│  │  RUN 1                 │  │  RUN 2                 │   ...   │
│  │  (one prompt→response) │  │  (next chat turn)     │         │
│  │                        │  │                        │         │
│  │  ┌────────┐ ┌────────┐ │  │  ┌────────┐           │         │
│  │  │Worker A│→│Worker B│ │  │  │Worker A│           │         │
│  │  │(entry) │ │(child) │ │  │  │(entry) │           │         │
│  │  └────────┘ └────────┘ │  │  └────────┘           │         │
│  └────────────────────────┘  └────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
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
llm-do project.json "first prompt"   # Session 1 (one run, then exit)
llm-do project.json "second prompt"  # Session 2 (separate process)
```

### Run Scope

**Lifetime**: One `runtime.run_entry()` call. One user prompt → one final response.

**What lives here**:
- The entry worker and any child workers it spawns
- Toolset instances (created per worker call, cleaned up after each call)
- Handle-based resources (DB transactions, browser sessions)

**When you have multiple runs**: Only in TUI **chat mode**. Each chat turn is a separate run within the same session.

```
Session (TUI with --chat)
├── Run 1: "Analyze this file"     → response
├── Run 2: "Now fix the bug"       → response  (new run, same session)
└── Run 3: "Write tests for it"    → response  (new run, same session)
```

In **headless mode** or **single-turn TUI**, session = run (one prompt, one response, exit).

**What is a run, really?**

A run is the execution of a single user request. It starts when the user submits a prompt and ends when the final response is returned. During a run:
1. The entry worker is invoked
2. It may call child workers (each gets its own `CallFrame`)
3. Tools are called, potentially creating handles
4. The final output is returned
5. Cleanup runs after each worker call (releasing handles, closing connections)

The key property: **all state created during a call is cleaned up immediately after that call**. This ensures that:
- Uncommitted DB transactions are rolled back
- Browser sessions are closed
- File handles are released
- The next run starts fresh

### Worker Scope

**Lifetime**: One worker execution within a run. A run may involve multiple workers.

**What lives here**:
- `CallFrame` (prompt, messages, depth, active toolsets)
- Per-call toolset instances
- Handle maps (e.g., `{txn_123: Connection}`)

**Why per-call isolation matters**:

Workers are LLM-controlled. Without isolation, Worker B could accidentally use Worker A's handles:
- LLM hallucinates a handle name that happens to exist
- Cross-worker state leakage causes unpredictable behavior

Per-call toolset instances ensure handles are invisible across nested calls.

## Scope Summary

| Scope | Lifetime | Created When | Cleaned Up When |
|-------|----------|--------------|-----------------|
| Session | Process lifetime | CLI/TUI starts | Process exits |
| Run | One prompt→response | `run_entry()` called | Response returned |
| Worker | One worker execution | Worker invoked | Worker returns |

## Implications for Toolset Design

When designing toolsets, consider which scope your state belongs to:

**Session-scoped** (rare):
- Truly stateless configuration
- Examples: shell command rules, static file paths

**Run-scoped**:
- Shared resources within a run
- Examples: connection pools, shared caches
- Must implement `cleanup()` to release at run end

**Worker-scoped** (most common):
- State that must be isolated between workers
- Examples: DB transactions, browser sessions, file handles
- Use the handle pattern for explicit state management
- Must implement `cleanup()` to release forgotten handles after each call

## The Chat Mode Exception

Chat mode (`--chat`) is the only case where multiple runs share a session. This enables:
- Message history continuity across turns
- Session-level approval caching (approve once, remember for session)

But run-scoped resources are still cleaned up between turns. Each chat turn is a fresh run with fresh toolset instances.

## See Also

- [architecture.md](architecture.md) - Runtime and CallFrame details
- [Task per-call-toolset-instances](../tasks/active/per-call-toolset-instances.md) - Per-call toolset instances implementation
