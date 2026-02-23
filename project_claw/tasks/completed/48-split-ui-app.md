# Split `LlmDoApp` UI Class

## Status
completed

## Prerequisites
- [x] `tasks/completed/47-split-context-class.md` (stabilize runtime boundary before UI split)

## Goal
Extract `LlmDoApp` responsibilities into composable components so the TUI can be replaced or tested without altering core message rendering and worker orchestration.

## Context
- Relevant files/symbols:
  - `llm_do/ui/app.py:24-200`: `LlmDoApp` class
  - `llm_do/ui/` directory: other UI components
  - `llm_do/ctx_runtime/cli.py`: creates and runs the app
- Related tasks/notes/docs:
  - `docs/notes/reviews/review-solid.md` (UI system finding)
  - `tasks/completed/47-split-context-class.md` (similar refactor for runtime)
- How to verify:
  - `uv run pytest`
  - Manual TUI smoke test
- Behaviors to preserve:
  - Message ordering and grouping matches current render order.
  - Approval batching stays consistent (no extra prompts, no missed approvals).
  - Input history navigation (up/down) preserves prior entries.
  - Worker lifecycle: spawn/cancel/complete state transitions remain correct.
  - UI remains responsive during worker runs (no blocking input loop).

## Decision Record
- Decision: Option A (extract composable controllers)
- Inputs:
  - `LlmDoApp` currently owns: UI composition, message rendering, approval batching, worker lifecycle management, user input history
  - Accumulation of stateful responsibilities (queues, tasks, history management, message buffers) makes the app hard to test
  - No interface boundary between presentation and orchestration
- Options:
  - A) Extract into composable widgets/controllers:
    - `InputHistoryManager` — command history, up/down navigation
    - `ApprovalWorkflowController` — approval queue, batching, user prompts
    - `WorkerRunner` — lifecycle management, task spawning
    - `MessageRenderer` — formatting, display
  - B) Keep monolithic but extract testable pure functions where possible
  - C) Full MVC/MVP split with abstract presenter interface
- Outcome:
  - Extracted UI-agnostic controllers under `llm_do/ui/controllers/`.
  - Updated `LlmDoApp` to delegate stateful logic to controllers.
  - Added unit tests for extracted controllers in `tests/ui/`.
- Follow-ups:
  - Consider whether `WorkerRunner` logic overlaps with `WorkerRuntime` from task 47

## Tasks
- [x] Audit `LlmDoApp` to inventory all responsibilities and state
- [x] Identify which responsibilities are presentation vs orchestration
- [x] Decide on decomposition approach (Option A/B/C)
- [x] Extract first component (`InputHistoryController`)
- [x] Extract approval workflow handling (`ApprovalWorkflowController`)
- [x] Extract worker lifecycle + message history management (`WorkerRunner`)
- [x] Update tests
- [x] Run `uv run pytest`

## Current State
Implemented controller extraction and updated the Textual TUI to use them. Updated CLI to avoid reaching into `LlmDoApp` private state, and verified with `uv run pytest`.

## Notes
- Single Responsibility pressure: one class doing UI composition + state management + orchestration
- Dependency Inversion pressure: no interface boundary, hard to swap presentation layer
- Goal is testability and swappability, not necessarily full framework adoption
- Keep Textual-specific code isolated so core logic could work with different UI frameworks
