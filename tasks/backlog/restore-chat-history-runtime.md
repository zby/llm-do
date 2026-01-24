# Restore chat history sync in Runtime

## Idea
Move message history syncing into `Runtime` so multi-turn chats preserve conversation state without `WorkerRuntime` owning the policy.

## Why
We removed entry message-history syncing to simplify the runtime surface. When we return to multi-agent chat, the entry/runtime layer should own conversation history so only the entry agent drives chat and nested agents remain stateless.

## Rough Scope
- Define how `Runtime.run_entry()` should own and update conversation history across turns.
- Decide the data flow: return a structured result or expose a runtime-managed history store.
- Update UI chat path to use the runtime-owned history (single agent owns chat).
- Add tests for multi-turn chat and verify nested agent calls do not inherit history.

## Why Not Now
We are simplifying the runtime surface and deferring multi-agent chat behavior.

## Trigger to Activate
When multi-agent chat or robust chat history becomes a priority.
