# Separate Calls from Turns

## Status
ready for implementation

## Prerequisites
- [ ] none

## Goal
Introduce CallScope and separate worker calls from turns so toolsets and message history persist across chat turns.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/call.py` (CallConfig, CallFrame; add CallScope)
  - `llm_do/runtime/worker.py` (Worker call path, toolset instantiation, chat path)
  - `llm_do/runtime/deps.py` (WorkerRuntime, spawn_child depth, run_chat_turn)
  - `llm_do/runtime/shared.py` (Runtime.run_entry, build_tool_plane)
  - `llm_do/ui/runner.py` (chat mode setup and cleanup)
- Related tasks/notes/docs: `docs/notes/call-scope-chat-locals.md`, `docs/notes/reviews/review-ctx-runtime.md`
- Inline background (from notes):
  - Chat currently re-enters `run_entry` per turn, rebuilding toolsets and call frames; desired model is a single CallFrame that persists across turns.
  - Toolsets should be created when entering a call and cleaned up when the call scope exits, not per turn.
  - Messages live directly on the CallFrame; remove parent-frame message mirroring for top-level workers.
  - Rebuild agent per turn; state lives on CallFrame (messages) + toolset instances.
  - Nested worker calls still create new CallFrames/toolsets (per-call locals).
  - Reset conversation is out of scope; when added it should create a new CallScope (fresh toolsets, empty messages).
  - Depth semantics: top-level worker calls start at depth 0, nested calls increment.
- How to verify / reproduce:
  - `uv run ruff check .`
  - `uv run mypy llm_do`
  - `uv run pytest`

## Decision Record
- Decision: Separate call vs turn with CallScope owned by Worker; no backcompat wrappers.
- Inputs:
  - Need persistent toolsets/messages across chat turns.
  - Simplify call/turn semantics and avoid parent-frame mirroring.
- Options:
  - Worker-owned CallScope vs Runtime helper; context manager vs explicit close; start runs first turn vs setup only.
- Outcome:
  - CallScope is an async context manager wrapping CallFrame; also expose `.close()` for non-`async with` use.
  - `worker.start(runtime)` only sets up and returns CallScope; all turns go through `scope.run_turn()`, including the first.
  - Runtime does not expose a chat-scope helper unless future entry types need it.
  - No parent entry frame for worker chat; update tests/logging for depth shift.
- Follow-ups:
  - Update any depth-sensitive logging/tests and chat UI to use CallScope.

## Tasks
- [ ] Add CallScope in `llm_do/runtime/call.py` to own CallFrame/toolsets and handle cleanup.
- [ ] Split worker execution into start/setup vs per-turn run; move toolset instantiation to start.
- [ ] Update chat path (UI runner and any runtime call sites) to use CallScope and reuse frame/messages.
- [ ] Remove parent-frame message mirroring and adjust depth/logging expectations.
- [ ] Add/adjust tests for CallScope lifecycle and chat turns; run lint/typecheck/tests.

## Current State
Moved from backlog; design decisions captured; no code changes yet.

## Notes
- Example usage:
  ```python
  async with worker.start(runtime) as scope:
      result = await scope.run_turn({"input": prompt})
      result = await scope.run_turn({"input": another_prompt})
  ```
- No backcompat required; prefer simplest sensible API.
