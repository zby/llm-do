# UI Architecture

The `llm_do/ui/` module provides the UI event pipeline for the async CLI. It separates
worker execution from rendering and keeps output consistent across Textual, Rich,
headless text, and JSON modes.

## Core Pipeline

```
Worker Events
  |
  v
parse_event()  -> UIEvent
  |
  v
Event Queue
  |
  v
DisplayBackend
  |-- TextualDisplayBackend (event.create_widget)
  |-- RichDisplayBackend (event.render_rich)
  |-- JsonDisplayBackend (event.render_json)
  `-- HeadlessDisplayBackend (event.render_text)
```

### UIEvent

`UIEvent` is the typed base class for all UI events. Each event renders itself into:
- Rich output (`render_rich`)
- Plain text (`render_text`, ASCII-only for system strings)
- JSON (`render_json`)
- Textual widget (`create_widget`)

### Event Parsing

Raw callback payloads are converted into typed events in one place:
- `llm_do/ui/parser.py` -> `parse_event(payload)`
- Approval requests use `parse_approval_request(request)` to emit an `ApprovalRequestEvent`

### DisplayBackend

Display backends are thin wrappers that call the appropriate `UIEvent` render method.
They optionally implement `start()`/`stop()` for setup and teardown.

### Textual TUI

`TextualDisplayBackend` forwards events to the Textual app via an async queue.
`LlmDoApp` is a thin consumer that only manages approval state and final output,
while `MessageContainer` handles streaming and widget mounting.

Approval requests are displayed in the TUI and resolved via an approval queue.
Non-interactive modes use `--approve-all` or `--strict` (or stdin prompts in headless
mode when available).

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

The worker's `message_callback` parses raw events and enqueues typed `UIEvent` objects.

## Files

| File | Purpose |
|------|---------|
| `llm_do/ui/events.py` | Typed UIEvent hierarchy |
| `llm_do/ui/parser.py` | Raw event parsing into UIEvent |
| `llm_do/ui/display.py` | DisplayBackend implementations |
| `llm_do/ui/app.py` | Textual TUI application (`LlmDoApp`) |
| `llm_do/ui/widgets/messages.py` | Message widgets and MessageContainer |

## Textual TUI

The default interactive mode uses Textual:

```
llm-do myworker "task"
```

### Architecture

```
Worker Events -> parse_event -> UIEvent queue -> TextualDisplayBackend -> LlmDoApp
                                                             |
                                                             v
                                                    MessageContainer
                                                        | | |
                                             Assistant  ToolCall  Approval
```

### Widgets

- `MessageContainer`: Scrollable container for all messages
- `AssistantMessage`: Streaming model responses
- `ToolCallMessage`: Tool invocation display
- `ToolResultMessage`: Tool result display
- `StatusMessage`: Status updates
- `ApprovalMessage`: Interactive approval requests

### Output Modes

| Mode | Flag | Backend | Interactivity | Notes |
|------|------|---------|---------------|-------|
| TUI (default) | — | TextualDisplayBackend + log buffer | Yes | Requires stdout TTY |
| JSON | `--json` | JsonDisplayBackend | No | Requires `--approve-all` or `--strict` |
| Headless (explicit) | `--headless` | HeadlessDisplayBackend | No | Prompts on stdin if TTY, otherwise requires approval flags |

**TUI Terminal History:** In TUI mode, events are captured to a Rich or plain-text
buffer (controlled by `--no-rich`) and printed after the TUI exits.

### TTY Detection

- **TTY present:** Textual TUI with interactive approvals.
- **No TTY:** Falls back to headless rendering. Rich output is used by default; use
  `--no-rich` for plain text. If stdin is not a TTY and no approval flags are set,
  headless mode defaults to strict behavior.

## Future Work

- **Streaming markdown**: Progressive markdown rendering in `AssistantMessage`
- **Deferred tools**: Real-time status updates for long-running tool execution
- **Multi-turn input**: Enable text input widget for conversation continuation
