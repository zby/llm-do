# Why Worker Execution Went Async

## Summary

We refactored the runtime to execute workers with native async (`agent.run`) instead of the layered `run_sync` + thread pool approach. The change removes a hard-to-debug hang that occurred whenever a worker called another worker that needed attachments. More importantly, it gives us a single, predictable event loop that nested workers, httpx clients, and file sandboxes can all share without contention.

## Background

Originally, the CLI always entered through `agent.run_sync()`. When a worker used `worker_call`, PydanticAI executed the tool inside an AnyIO worker thread. That thread then invoked `run_worker()` which tried to spin up *another* `run_sync()` and, in turn, another event loop. As soon as the nested worker attempted to upload attachments, the loop deadlocked (`asyncio.run()` blocks inside a non-main thread with no running loop). The reproduction script (`reproduce_hang.py`) and the `whiteboard_orchestrator → whiteboard_planner` example both stalled right after printing "Calling anthropic:claude-haiku-4-5...".

## Why the old design failed

- `run_sync()` assumes it owns the event loop; inside AnyIO worker threads that assumption is false, so nested workers get their own orphaned loop and hang.
- httpx.AsyncClient binds to the thread/loop where it is created; nested workers inherited sockets tied to a loop that never advanced.
- Attempted mitigations—loop detection, creating agents inside the worker thread, custom event-loop policy, even wrapping `agent.run()` in a new `asyncio.run()`—only shuffled the deadlock around because the underlying problem (stacking sync shims inside async tooling) remained.

## Design change

- **Single async surface area**: The CLI now enters via `asyncio.run(main())`, and every worker path stays async all the way down. We never call `run_sync()`.
- **Explicit loop ownership**: `run_worker` is `async`, so nested workers simply await each other within the same AnyIO task tree instead of bouncing through thread pools.
- **Shared clients/sandboxes**: httpx clients, attachment streaming, and approval callbacks all run on the same loop, which prevents resource binding issues. This made the hanging reproduction disappear immediately.

## Benefits

1. **Reliability** – Nested workers (and future chains of workers) no longer risk deadlocks from loop confusion.
2. **Better composability** – `worker_call` can be awaited like any other coroutine, making orchestration workers easier to reason about and test.
3. **Performance headroom** – We can keep long-lived connections per loop and schedule multiple workers concurrently without shipping work off to ad-hoc threads.
4. **Clearer ergonomics** – Tool authors implement `async def` by default, which matches how PydanticAI already prefers to run tools.

## Migration notes

- CLI entrypoints use `.venv/bin/python -m llm_do.cli` which calls `asyncio.run(main())`.
- `run_worker` and all code that previously assumed sync execution are now async; callers either run inside the CLI event loop or use `anyio.run(run_worker, ...)` in tests.
- `reproduce_hang.py` remains as a regression test harness; running it against the async runtime confirms the nested worker now completes instead of hanging.

Async-by-default removes a whole class of orchestration bugs and unlocks features like streaming and concurrent approvals. It is the long-term direction for llm-do, and this bug was the forcing function that made the redesign urgent.
