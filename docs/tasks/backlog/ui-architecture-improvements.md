# UI Architecture Improvements

## Idea
Refine the UI event/rendering architecture to reduce per-event boilerplate, improve SOLID alignment, and tighten test coverage while keeping the current event flow.

## Why
The current "events render themselves" model is clean for adding new events but couples events to Rich/Textual and requires each event to implement every output format. This makes new output formats and streaming behaviors harder to evolve.

## Rough Scope
- Introduce default rendering (text required, rich/json defaulted) to cut boilerplate.
- Evaluate separating renderers (Rich/Text/JSON/Widget) from event data for DIP/OCP.
- Add a small streaming protocol to reduce `isinstance` branching in TUI.
- Add targeted Textual tests for streaming + approval flow.
- Update `docs/ui.md` to reflect the current typed-event architecture.

## Why Not Now
- Active UI reimplementation work already in progress; avoid scope creep.
- Requires design decisions that should be made with concrete future output formats in mind.

## Trigger to Activate
- A new output backend is requested (e.g., HTML/web or log ingestion).
- Repeated pain adding new events or streaming behaviors.
- Need for stronger test guarantees on TUI/approval paths.
