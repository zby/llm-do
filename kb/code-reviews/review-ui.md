---
description: Periodic review findings for the UI system.
---

# UI System Review

## Context
Review of the UI system for bugs, inconsistencies, and overengineering.

## Findings
- Streaming is consistent across headless/rich backends: deltas print inline (no
  newline per chunk) and a final `TextResponseEvent(is_complete=True)` is emitted
  after streaming completes. (`llm_do/ui/display.py`, `llm_do/ui/events.py`,
  `llm_do/runtime/worker.py`)
- The TUI message widgets render assistant/tool content as literal text
  (`markup=False`) to avoid markup injection and match headless output.
  (`llm_do/ui/widgets/messages.py`)
- Tool call/result rendering is robust: JSON formatting uses `default=str` and
  truncation is applied to large payloads. (`llm_do/ui/widgets/messages.py`,
  `llm_do/ui/events.py`)
- TUI responsibilities are reasonably decomposed: approval queueing, worker task
  lifecycle, input history, and exit confirmation are handled by small
  controllers rather than bloating `LlmDoApp`. (`llm_do/ui/controllers/*`,
  `llm_do/ui/app.py`)
- Minor duplication remains in the rendering stack: events own render methods,
  but backends still special-case streaming deltas (`end=""` / newline
  suppression). This isn’t a correctness issue, but it complicates the mental
  model of “events render themselves”. (`llm_do/ui/events.py`,
  `llm_do/ui/display.py`)

## Open Questions
- Should streaming formatting be handled entirely by the display backends (so
  `TextResponseEvent.render_*` stays purely declarative), or should backends stop
  special-casing deltas?
- In TUI mode, should we avoid double-sending the render-loop sentinel (`None`)
  to keep queue semantics simpler? (`llm_do/cli/main.py`)
- Do we want approval requests logged into TUI scrollback (in addition to the
  pinned approval panel), for parity with headless/rich transcripts?

## Conclusion
UI is in a healthier state: streaming, truncation, and literal rendering are
aligned across backends, and TUI state is split into small controllers. Remaining
work is mostly about simplifying the rendering responsibility boundaries.

## Review 2026-02-01

### Findings
- **Chat history is not applied to runtime:** TUI collects `message_history` between turns, but `Runtime.run_entry` never forwards that history into the entry agent. Chat turns are effectively stateless even though the UI shows a conversation. (`llm_do/ui/runner.py`, `llm_do/runtime/runtime.py`, `llm_do/runtime/context.py`)
- **Chat mode requires an initial prompt:** `run_tui` errors if `chat=True` and no initial prompt is provided, which blocks starting an empty chat session. (`llm_do/ui/runner.py`)

### Open Questions
- Should chat mode allow a blank initial prompt (start idle and wait for user input)?
- Should message history be owned by the runtime (and always forwarded), or stay UI-only until a runtime-level sync model exists?

### Conclusion
Chat UX still diverges from multi-turn expectations; history plumbing and initial-prompt rules need a decision.
