# UI Architecture

The `llm_do/ui/` module provides the UI event pipeline for the runtime CLI. It separates worker execution from rendering and keeps output consistent across Textual and headless text modes.

## Core Pipeline

```
Worker Events
  |
  v
runtime parse_event() -> RuntimeEvent
  |
  v
adapt_event() -> UIEvent
  |
  v
Event Queue
  |
  v
DisplayBackend
  |-- TextualDisplayBackend (event.create_widget)
  |-- HeadlessDisplayBackend (event.render_text)
  `-- RichDisplayBackend (event.render_rich, log buffer)
```

### UIEvent

`UIEvent` is the typed base class for all UI events. Each event renders itself into:
- Plain text (`render_text`, ASCII-only for system strings)
- Textual widget (`create_widget`)
- Rich output (`render_rich`)

### Event Parsing + Adaptation

Raw callback payloads are converted into runtime events and then adapted for UI:
- `llm_do/runtime/event_parser.py` -> `parse_event(payload)` returns `RuntimeEvent`
- `llm_do/ui/adapter.py` -> `adapt_event(runtime_event)` returns `UIEvent`
- Approval requests use `llm_do/ui/parser.py` -> `parse_approval_request(request)`

### DisplayBackend

Display backends are thin wrappers that call the appropriate `UIEvent` render method.
They optionally implement `start()`/`stop()` for setup and teardown.

### Textual TUI

`TextualDisplayBackend` forwards events to the Textual app via an async queue.
`LlmDoApp` orchestrates the TUI and delegates stateful logic to controllers
(approval batching, input history, exit confirmation, worker runs), while
`MessageContainer` handles streaming and widget mounting.

Approval requests are displayed in the TUI and resolved via `ApprovalWorkflowController`.
Non-interactive modes should use `--approve-all` when approvals are required.

## Event Flow

```python
async def _render_loop(queue: asyncio.Queue, backend: DisplayBackend) -> None:
    await backend.start()
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            backend.display(event)
            queue.task_done()
    finally:
        await backend.stop()
```

The runtime event stream handler parses raw events into `RuntimeEvent` objects, and the UI adapter converts them to `UIEvent` instances for rendering.

## Files

| File | Purpose |
|------|---------|
| `llm_do/ui/events.py` | Typed UIEvent hierarchy |
| `llm_do/runtime/events.py` | Runtime event types |
| `llm_do/runtime/event_parser.py` | Raw event parsing into RuntimeEvent |
| `llm_do/ui/adapter.py` | RuntimeEvent -> UIEvent adapter |
| `llm_do/ui/parser.py` | Approval request parsing |
| `llm_do/ui/display.py` | DisplayBackend implementations |
| `llm_do/ui/app.py` | Textual TUI application (`LlmDoApp`) |
| `llm_do/ui/controllers/` | UI-agnostic controllers used by the Textual app |
| `llm_do/ui/widgets/messages.py` | Message widgets and MessageContainer |

### Controllers

`llm_do/ui/controllers/` holds UI-agnostic state used by the Textual app:
- `ApprovalWorkflowController` — approval queue + batch numbering
- `InputHistoryController` — input history navigation and draft preservation
- `ExitConfirmationController` — double-quit confirmation state
- `WorkerRunner` — background task tracking + message history storage

## Textual TUI

The default interactive mode uses Textual when stdout is a TTY:

```
llm-do main.agent "task"
```

### Architecture

```
Worker Events -> runtime parse_event -> RuntimeEvent -> adapt_event -> UIEvent queue -> TextualDisplayBackend -> LlmDoApp
                                                             |
                                                             v
                                                       Controllers
                                                            |
                                                            v
                                                    MessageContainer
                                                        | |
                                             Assistant  ToolCall
                                                       |
                                                  ApprovalPanel
```

### Widgets

- `MessageContainer`: Scrollable container for all messages
- `AssistantMessage`: Streaming model responses
- `ToolCallMessage`: Tool invocation display
- `ToolResultMessage`: Tool result display
- `StatusMessage`: Status updates
- `ApprovalPanel`: Pinned approval requests panel

### Output Modes

| Mode | Flag | Backend | Interactivity | Notes |
|------|------|---------|---------------|-------|
| TUI (default) | — | TextualDisplayBackend + log buffer | Yes | Requires stdout TTY |
| Headless | `--headless` | HeadlessDisplayBackend | No | Events to stderr with `-v`/`-vv`, final output to stdout |

**TUI Terminal History:** In TUI mode, events are captured to a Rich log buffer and printed to stderr after the TUI exits.

### TTY Detection

- **TTY present:** Textual TUI with interactive approvals.
- **No TTY:** Falls back to headless rendering. Use `-v` or `-vv` for event output.
- **Force modes:** `--tui` forces interactive UI; `--headless` disables it.

### Chat Mode

Use `--chat` to keep the TUI open for multi-turn conversations:

```
llm-do main.agent "hello" --chat
```

Input behavior in chat mode:
- `Enter` inserts a newline.
- `Ctrl+J` sends the message.
- Input stays disabled in single-turn mode; the app exits automatically on completion.

## Future Work

- **Streaming markdown**: Progressive markdown rendering in `AssistantMessage`
- **Deferred tools**: Real-time status updates for long-running tool execution
- **Input UX**: Tighter shortcuts, sizing, and draft persistence polish
