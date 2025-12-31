# Split `LlmDoApp` UI Class

## Status
information gathering

## Prerequisites
- [ ] `docs/tasks/active/47-split-context-class.md` (stabilize runtime boundary before UI split)

## Goal
Extract `LlmDoApp` responsibilities into composable components so the TUI can be replaced or tested without altering core message rendering and worker orchestration.

## Context
- Relevant files/symbols:
  - `llm_do/ui/app.py:24-200`: `LlmDoApp` class
  - `llm_do/ui/` directory: other UI components
  - `llm_do/ctx_runtime/cli.py`: creates and runs the app
- Related tasks/notes/docs:
  - `docs/notes/reviews/review-solid.md` (UI system finding)
  - `docs/tasks/active/47-split-context-class.md` (similar refactor for runtime)
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
- Decision: TBD
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
- Outcome: TBD
- Follow-ups:
  - Consider whether `WorkerRunner` logic overlaps with `WorkerRuntime` from task 47

## Tasks
- [ ] Audit `LlmDoApp` to inventory all responsibilities and state
- [ ] Identify which responsibilities are presentation vs orchestration
- [ ] Decide on decomposition approach (Option A/B/C)
- [ ] Extract first component (likely `InputHistoryManager` — smallest, clearest boundary)
- [ ] Extract approval workflow handling
- [ ] Extract worker lifecycle management
- [ ] Update tests
- [ ] Run `uv run pytest`

## Current State
Task created from SOLID review. No implementation started.

## Notes
- Single Responsibility pressure: one class doing UI composition + state management + orchestration
- Dependency Inversion pressure: no interface boundary, hard to swap presentation layer
- Goal is testability and swappability, not necessarily full framework adoption
- Keep Textual-specific code isolated so core logic could work with different UI frameworks
