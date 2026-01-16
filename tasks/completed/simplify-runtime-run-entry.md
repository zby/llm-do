# Simplify Runtime.run_entry setup

## Status
completed

## Prerequisites
- [ ] none

## Goal
Remove the redundant `Worker.model` None check in `Runtime.run_entry` and
consolidate the duplicated frame/context/event setup between entry branches.

## Context
- Relevant files/symbols:
  - `llm_do/runtime/shared.py` - `Runtime.run_entry`, `_build_entry_frame`
  - `llm_do/runtime/worker.py` - `Worker.__post_init__`, `Worker`
  - `llm_do/runtime/events.py` - `UserMessageEvent`
- Related tasks/notes/docs:
  - `docs/notes/reviews/simplify-runtime-runner.md`
- How to verify / reproduce:
  - `uv run pytest`

Key snippet (current state in `Runtime.run_entry`):
```python
if isinstance(invocable, Worker):
    if invocable.model is None:
        raise NoModelError(...)
    frame = self._build_entry_frame(...)
    frame.prompt = prompt_spec.text
    ctx = WorkerRuntime(runtime=self, frame=frame)
    if self._config.on_event is not None:
        self._config.on_event(UserMessageEvent(...))
    result = await ctx._execute(invocable, input_args)
    return result, ctx
```

EntryFunction branch mirrors the frame/prompt/context/event setup.

`Worker.__post_init__` calls `select_model(...)`, which raises `NoModelError` if
no model is configured. If `Worker.model` is treated as immutable after init,
the guard above is redundant.

## Decision Record
- Decision: treat `Worker.model` as immutable after `__post_init__`.
- Inputs: `Worker.__post_init__` resolves model or raises; current runtime still
  checks for None in `Runtime.run_entry`.
- Options:
  - Remove the guard and rely on `Worker.__post_init__`. (selected)
  - Keep the guard to protect against post-init mutation.
  - Replace guard with a clear assertion + comment.
- Outcome: remove the redundant `invocable.model is None` guard; use a local
  closure in `Runtime.run_entry` to consolidate frame/prompt/context/event
  setup; add brief comments explaining the shared setup and the immutability
  assumption.
- Follow-ups:
  - Confirm no tests rely on `Runtime.run_entry` raising `NoModelError` for
    mutated workers.
  - Add short comments in code near the shared setup helper.

## Tasks
- [x] Confirm no callers set `worker.model = None` after initialization.
- [x] Remove redundant `invocable.model is None` guard.
- [x] Extract shared setup for frame/prompt/context/event between
  EntryFunction and Worker branches (local closure) with brief comments.
- [x] Update tests/docs if behavior changes.

## Current State
Implemented shared entry setup helper and removed redundant guard in
`Runtime.run_entry`; awaiting checks.

## Notes
- Avoid over-abstracting; helper should only handle the repeated setup.
- Ensure `UserMessageEvent` still emits once per entry with identical content.
