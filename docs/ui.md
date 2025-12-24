# UI Architecture

The `llm_do/ui/` module provides the UI event pipeline for the ctx_runtime CLI. It separates worker execution from rendering and keeps output consistent across Textual, headless text, and JSON modes.

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
  |-- JsonDisplayBackend (event.render_json)
  |-- HeadlessDisplayBackend (event.render_text)
  `-- RichDisplayBackend (event.render_rich, log buffer)
```

### UIEvent

`UIEvent` is the typed base class for all UI events. Each event renders itself into:
- Plain text (`render_text`, ASCII-only for system strings)
- JSON (`render_json`)
- Textual widget (`create_widget`)
- Rich output (`render_rich`)

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

The default interactive mode uses Textual when stdout is a TTY:

```
llm-run main.worker "task"
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
| Headless | `--headless` | HeadlessDisplayBackend | No | Events to stderr with `-v`/`-vv`, final output to stdout |
| JSON | `--json` | JsonDisplayBackend | No | JSONL event stream to stderr; cannot combine with `--tui` |

**TUI Terminal History:** In TUI mode, events are captured to a Rich log buffer and printed to stderr after the TUI exits.

### TTY Detection

- **TTY present:** Textual TUI with interactive approvals.
- **No TTY:** Falls back to headless rendering. Use `-v` or `-vv` for event output.
- **Force modes:** `--tui` forces interactive UI; `--headless` disables it.

## Future Work

- **Streaming markdown**: Progressive markdown rendering in `AssistantMessage`
- **Deferred tools**: Real-time status updates for long-running tool execution
- **Multi-turn input**: Enable text input widget for conversation continuation
