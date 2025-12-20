# UI Architecture

The `llm_do/ui/` module provides display abstractions for the async CLI, separating rendering logic from the core worker execution.

## Display Backends

The CLI uses a `DisplayBackend` abstraction to render events. This allows swapping between Textual TUI (interactive terminal) and JSON (automation/scripting) output without changing the event flow.

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Worker Events  │────▶│  Event Queue │────▶│    DisplayBackend   │
└─────────────────┘     └──────────────┘     └─────────────────────┘
                                                        │
                                               ┌────────┴────────┐
                                               ▼                 ▼
                                    TextualDisplayBackend  JsonDisplayBackend
```

### CLIEvent

All events flowing through the display system are wrapped in `CLIEvent`:

```python
@dataclass
class CLIEvent:
    kind: Literal["runtime_event", "deferred_tool", "approval_request"]
    payload: Any
```

- **runtime_event**: Standard pydantic-ai message events (text, tool calls, tool results)
- **deferred_tool**: Deferred/async tool execution status updates
- **approval_request**: Tool approval requests (TUI-only, see note below)

### DisplayBackend (ABC)

Base class for all display backends:

```python
class DisplayBackend(ABC):
    wants_runtime_events: bool = True  # Set False to skip event streaming

    async def start(self) -> None: ...   # Called before event loop
    async def stop(self) -> None: ...    # Called after event loop

    def handle_event(self, event: CLIEvent) -> None: ...  # Route to handlers

    @abstractmethod
    def display_runtime_event(self, payload: Any) -> None: ...

    @abstractmethod
    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None: ...
```

**Note on approval_request**: The `approval_request` event kind is handled directly by the
Textual TUI (`LlmDoApp`) and bypasses the `DisplayBackend` abstraction. Non-interactive
backends (JSON, headless) require `--approve-all` or `--strict` flags, so they never
receive approval requests.

### TextualDisplayBackend

Forwards events to the Textual TUI application via an async queue:

- Wraps events as `CLIEvent` and enqueues for `LlmDoApp` consumption
- The TUI handles rendering, streaming text, and interactive approvals
- Approval requests flow through a separate queue for response handling

### JsonDisplayBackend

Machine-readable JSONL output for automation:

- Writes newline-delimited JSON records to stderr
- Each record includes `kind` and `payload` fields
- Handles Pydantic models via `model_dump()`

## Event Flow

The async CLI sets up a render loop that consumes events from a queue:

```python
async def _render_loop(queue: asyncio.Queue, backend: DisplayBackend) -> None:
    await backend.start()
    try:
        while True:
            payload = await queue.get()
            if payload is None:  # Sentinel to stop
                break
            if isinstance(payload, CLIEvent):
                backend.handle_event(payload)
            queue.task_done()
    finally:
        await backend.stop()
```

The worker's `message_callback` enqueues events directly (no thread-safety wrapper needed since everything runs in the same event loop).

## Files

| File | Purpose |
|------|---------|
| `llm_do/ui/__init__.py` | Public exports |
| `llm_do/ui/display.py` | DisplayBackend abstraction and implementations |
| `llm_do/ui/app.py` | Textual TUI application (`LlmDoApp`) |
| `llm_do/ui/widgets/messages.py` | Message display widgets for TUI |

## Textual TUI

The default interactive mode uses Textual for a rich terminal UI:

```
llm-do myworker "task"
```

### Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Worker Events  │────▶│  Event Queue │────▶│ TextualDisplayBackend│
└─────────────────┘     └──────────────┘     └─────────────────────┘
                                                       │
                                                       ▼
                                               ┌─────────────┐
                                               │  LlmDoApp   │
                                               └─────────────┘
                                                       │
                                      ┌────────────────┼────────────────┐
                                      ▼                ▼                ▼
                               AssistantMessage  ToolCallMessage  ApprovalMessage
```

### Widgets

- `MessageContainer`: Scrollable container for all messages
- `AssistantMessage`: Streaming model responses
- `ToolCallMessage`: Tool invocation display
- `ToolResultMessage`: Tool result display
- `StatusMessage`: Status updates
- `ApprovalMessage`: Interactive approval requests

### Output Modes

| Flag | Backend | Interactivity | Use Case |
|------|---------|---------------|----------|
| (default) | TextualDisplayBackend | Yes (requires TTY) | Interactive terminal |
| `--json` | JsonDisplayBackend | No | Automation/scripting |
| `--headless` | (plain text) | No | CI/CD, pipes |

### TTY Detection

The CLI auto-detects whether it's running in an interactive terminal:
- **TTY present**: Rich output with interactive approval prompts
- **No TTY**: Requires `--approve-all` or `--strict` for approval handling

## Future Work

- **Streaming text**: Progressive text rendering during model output
- **Deferred tools**: Real-time status updates for long-running tool execution
- **Multi-turn input**: Enable text input widget for conversation continuation
