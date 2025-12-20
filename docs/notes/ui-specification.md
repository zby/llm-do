# UI System Specification

This document provides a detailed specification of the llm-do UI system, sufficient for reimplementation.

## Overview

The UI system displays worker execution events in real-time. It supports four output modes:
1. **TUI** - Interactive Textual terminal application (default)
2. **Rich** - Colorful formatted text (non-interactive)
3. **Headless** - Plain text (non-interactive)
4. **JSON** - Machine-readable JSONL (non-interactive)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Worker Execution                             │
│  (pydantic-ai agent runs, emits events via message_callback)        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Event Queue                                  │
│  asyncio.Queue[CLIEvent | None]                                     │
│  - CLIEvent wraps all events with kind + payload                    │
│  - None is sentinel signaling worker completion                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DisplayBackend (ABC)                            │
│  - handle_event(CLIEvent) → routes to display_* methods             │
│  - display_runtime_event(payload) → handles worker events           │
│  - display_deferred_tool(payload) → handles deferred tool updates   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ TextualBackend│     │  RichBackend    │     │  JsonBackend    │
│ (→ TUI App)   │     │  (Rich Console) │     │  (JSONL)        │
└───────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                      ┌─────────────────┐
                      │HeadlessBackend  │
                      │ (plain text)    │
                      └─────────────────┘
```

## Event Types

### CLIEvent

```python
@dataclass
class CLIEvent:
    kind: Literal["runtime_event", "deferred_tool", "approval_request"]
    payload: Any
```

### Event Kinds

1. **runtime_event** - Standard worker execution events:
   - Initial request preview
   - Status updates (phase/state/model)
   - PydanticAI message events (text parts, tool calls, tool results)

2. **deferred_tool** - Async tool execution status:
   - `tool_name`: str
   - `status`: str ("pending", "running", "complete", "error")

3. **approval_request** - Tool approval requests (TUI only):
   - `ApprovalRequest` object from pydantic-ai-blocking-approval

### Runtime Event Payload Structure

Events come as dicts from the message callback:

```python
# Initial request
{
    "worker": "worker_name",
    "initial_request": {
        "instructions": "...",
        "user_input": "...",
        "attachments": [...]
    }
}

# Status update
{
    "worker": "worker_name",
    "status": {
        "phase": "model_request",
        "state": "start" | "end" | "error",
        "model": "anthropic:claude-haiku-4-5",
        "duration_sec": 1.23  # optional
    }
}

# PydanticAI event
{
    "worker": "worker_name",
    "event": <pydantic_ai.messages.* event object>
}
```

### PydanticAI Event Types

From `pydantic_ai.messages`:

| Event | Description | Display Action |
|-------|-------------|----------------|
| `PartStartEvent` | New part starting | Start new message widget (text) or prepare for tool call |
| `PartDeltaEvent` | Streaming text chunk | Append to current message (if streaming enabled) |
| `PartEndEvent` | Part complete | Display complete text response |
| `FunctionToolCallEvent` | Tool invocation | Display tool name + args |
| `FunctionToolResultEvent` | Tool result | Display tool result content |
| `FinalResultEvent` | Agent finished | Display completion indicator |

## Display Backends

### DisplayBackend (Abstract Base)

```python
class DisplayBackend(ABC):
    wants_runtime_events: bool = True  # Set False to skip event streaming

    async def start(self) -> None: ...   # Called before event loop
    async def stop(self) -> None: ...    # Called after event loop

    def handle_event(self, event: CLIEvent) -> None:
        # Routes to display_runtime_event or display_deferred_tool

    @abstractmethod
    def display_runtime_event(self, payload: Any) -> None: ...

    @abstractmethod
    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None: ...
```

### TextualDisplayBackend

Forwards events to Textual TUI application via async queue.

```python
class TextualDisplayBackend(DisplayBackend):
    def __init__(self, event_queue: asyncio.Queue[Any]):
        self._queue = event_queue

    def display_runtime_event(self, payload: Any) -> None:
        self._queue.put_nowait(CLIEvent(kind="runtime_event", payload=payload))

    def display_deferred_tool(self, payload: Mapping[str, Any]) -> None:
        self._queue.put_nowait(CLIEvent(kind="deferred_tool", payload=payload))
```

### RichDisplayBackend

Colorful formatted output using Rich Console.

```python
class RichDisplayBackend(DisplayBackend):
    def __init__(
        self,
        stream: TextIO | None = None,      # Default: sys.stderr
        force_terminal: bool = False,       # Force ANSI codes for non-TTY
        verbosity: int = 0,                 # 0=minimal, 1=normal, 2=verbose
    ): ...
```

**Color Scheme:**
- Worker names: `[bold cyan]` (starting), `[dim]` (status), `[bold green]` (response), `[bold yellow]` (tool call), `[bold blue]` (tool result)
- Tool names: `[yellow]` (calls), `[blue]` (results)
- Status: `[dim]` for phases and models
- Completion: `[green]✓[/green]`

**Verbosity Levels:**
- 0 (minimal): Prompts, responses, tool calls/results, status
- 1 (normal): Add "Generating...", "Complete" indicators
- 2 (verbose): Add streaming deltas as they arrive

**Truncation:**
- User input: 200 chars
- Tool args: 200 chars
- Tool results: 500 chars, 10 lines max

### HeadlessDisplayBackend

Plain text output (no ANSI codes).

```python
class HeadlessDisplayBackend(DisplayBackend):
    def __init__(
        self,
        stream: TextIO | None = None,      # Default: sys.stderr
        verbosity: int = 0,                 # Same levels as Rich
    ): ...
```

**Format:**
```
[worker_name] Starting...
  Prompt: user input here
[worker_name] model_request start (anthropic:claude-haiku-4-5)

[worker_name] Tool call: tool_name
  Args: {"key": "value"}

[worker_name] Tool result: tool_name
  result content here

[worker_name] Response:
  The assistant's response
  spanning multiple lines
```

### JsonDisplayBackend

Machine-readable JSONL output.

```python
class JsonDisplayBackend(DisplayBackend):
    def __init__(self, stream: TextIO | None = None): ...  # Default: sys.stderr
```

**Output Format:**
```jsonl
{"kind": "runtime_event", "payload": {...}}
{"kind": "deferred_tool", "payload": {"tool_name": "...", "status": "..."}}
```

Handles non-JSON types:
- Pydantic models: `.model_dump()`
- Objects with `.dict()`: `.dict()`
- Fallback: `repr()`

## Textual TUI Application

### LlmDoApp

Main Textual application class.

```python
class LlmDoApp(App[None]):
    def __init__(
        self,
        event_queue: asyncio.Queue[Any],
        approval_response_queue: asyncio.Queue[ApprovalDecision] | None = None,
        worker_coro: Any | None = None,
        auto_quit: bool = True,
    ): ...
```

**Constructor Parameters:**
- `event_queue`: Receives CLIEvent objects from worker
- `approval_response_queue`: Sends ApprovalDecision back to worker
- `worker_coro`: Optional coroutine to run as background task
- `auto_quit`: Exit automatically when worker completes

**Instance State:**
- `_pending_approval`: Current ApprovalRequest awaiting response
- `_worker_task`: Background task running worker_coro
- `_done`: Boolean flag for completion
- `_messages`: List[str] capturing response text
- `final_result`: Joined messages for post-exit display

### Layout

```
┌─────────────────────────────────────────────────┐
│                   Header                         │  show_clock=True
├─────────────────────────────────────────────────┤
│                                                 │
│              MessageContainer                    │  Scrollable, grows
│              (id="messages")                     │
│                                                 │
├─────────────────────────────────────────────────┤
│  Input (disabled)                               │  Placeholder for future
│  (id="user-input")                              │
├─────────────────────────────────────────────────┤
│                   Footer                         │  Key bindings
└─────────────────────────────────────────────────┘
```

**CSS Grid:**
```css
Screen {
    layout: grid;
    grid-size: 1;
    grid-rows: 1fr auto auto;
}
```

### Key Bindings

| Key | Action | Description |
|-----|--------|-------------|
| `q` | `action_quit` | Quit application |
| `a` | `action_approve` | Approve current tool once |
| `s` | `action_approve_session` | Approve tool for session |
| `d` | `action_deny` | Deny current tool |

### Event Consumer Loop

```python
async def _consume_events(self) -> None:
    messages = self.query_one("#messages", MessageContainer)

    while not self._done:
        try:
            event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue

        if event is None:  # Sentinel
            self._done = True
            if self._messages:
                self.final_result = "\n".join(self._messages)
            if self._auto_quit:
                self.exit()
            break

        # Route CLIEvent by kind
        if event.kind == "runtime_event":
            self._handle_runtime_event(event.payload, messages)
        elif event.kind == "deferred_tool":
            self._handle_deferred_tool(event.payload, messages)
        elif event.kind == "approval_request":
            await self._handle_approval_request(event.payload, messages)
```

## Message Widgets

All widgets inherit from `BaseMessage(Static)`.

### BaseMessage

```python
class BaseMessage(Static):
    DEFAULT_CSS = """
    BaseMessage {
        width: 100%;
        padding: 1;
        margin: 0 0 1 0;
    }
    """
```

### AssistantMessage

For streaming/complete model responses.

```python
class AssistantMessage(BaseMessage):
    DEFAULT_CSS = """
    AssistantMessage {
        background: $primary-background;
        border: solid $primary;
    }
    """

    def __init__(self, content: str = "", **kwargs): ...
    def append_text(self, text: str) -> None:
        self._content += text
        self.update(self._content)
```

### ToolCallMessage

For tool invocations.

```python
class ToolCallMessage(BaseMessage):
    DEFAULT_CSS = """
    ToolCallMessage {
        background: $warning-darken-3;
        border: solid $warning;
    }
    """

    def __init__(self, tool_name: str, tool_call: Any, **kwargs): ...
```

**Display Format:**
```
[bold yellow]Tool: tool_name[/bold yellow]
Args: {"key": "value", ...}
```

### ToolResultMessage

For tool results.

```python
class ToolResultMessage(BaseMessage):
    DEFAULT_CSS = """
    ToolResultMessage {
        background: $success-darken-3;
        border: solid $success;
    }
    """

    def __init__(self, tool_name: str, result: Any, **kwargs): ...
```

**Display Format:**
```
[bold green]Result: tool_name[/bold green]
result content (truncated to 500 chars)
```

### StatusMessage

For status updates.

```python
class StatusMessage(BaseMessage):
    DEFAULT_CSS = """
    StatusMessage {
        color: $text-muted;
        padding: 0 1;
        margin: 0;
        background: transparent;
        border: none;
    }
    """
```

### ApprovalMessage

For interactive approval requests.

```python
class ApprovalMessage(BaseMessage):
    DEFAULT_CSS = """
    ApprovalMessage {
        background: $error-darken-3;
        border: solid $error;
    }
    """

    def __init__(self, request: ApprovalRequest, **kwargs): ...
```

**Display Format:**
```
[bold red]Approval Required: tool_name[/bold red]

Reason: description text

Arguments:
{
  "arg1": "value1"
}

[green][[a]][/green] Approve once
[green][[s]][/green] Approve for session
[red][[d]][/red] Deny
[red][[q]][/red] Quit
```

### MessageContainer

Scrollable container managing message widgets.

```python
class MessageContainer(ScrollableContainer):
    def __init__(self, **kwargs):
        self._current_assistant: AssistantMessage | None = None

    def start_assistant_message(self) -> AssistantMessage:
        # Creates new AssistantMessage, mounts, scrolls to end

    def append_to_assistant(self, text: str) -> None:
        # Appends to current or creates new

    def add_tool_call(self, tool_name: str, tool_call: Any) -> ToolCallMessage:
        # Ends streaming, mounts ToolCallMessage

    def add_tool_result(self, tool_name: str, result: Any) -> ToolResultMessage:
        # Mounts ToolResultMessage

    def add_status(self, text: str) -> StatusMessage:
        # Mounts StatusMessage with [dim] wrapper

    def add_approval_request(self, request: ApprovalRequest) -> ApprovalMessage:
        # Ends streaming, mounts ApprovalMessage
```

**Auto-scroll:** All add methods call `self.scroll_end(animate=False)`.

## CLI Integration

### TUI Mode Flow

```python
async def _run_tui_mode(args):
    # 1. Create queues
    event_queue = asyncio.Queue()
    approval_queue = asyncio.Queue()

    # 2. Create backends
    tui_backend = TextualDisplayBackend(event_queue)

    # 3. Create buffer for terminal history
    output_buffer = io.StringIO()
    rich_backend = RichDisplayBackend(output_buffer, force_terminal=True)

    # 4. Create combined message callback
    def combined_callback(events):
        for event in events:
            event_queue.put_nowait(CLIEvent(kind="runtime_event", payload=event))
            rich_backend.display_runtime_event(event)

    # 5. Run worker as background coroutine
    async def run_worker():
        result = await run_worker_async(..., message_callback=combined_callback)
        event_queue.put_nowait(None)  # Sentinel
        return result

    # 6. Create and run TUI app
    app = LlmDoApp(event_queue, approval_queue, worker_coro=run_worker())
    await app.run_async(mouse=False)

    # 7. Print captured output after TUI exits
    print(output_buffer.getvalue())
```

### Headless/Rich Mode Flow

```python
async def _run_headless_mode(args):
    # 1. Create queue and backend
    queue = asyncio.Queue()
    if args.rich:
        backend = RichDisplayBackend(force_terminal=True)
    else:
        backend = HeadlessDisplayBackend()

    # 2. Start render loop
    renderer = asyncio.create_task(_render_loop(queue, backend))

    # 3. Run worker with callback
    result = await run_worker_async(..., message_callback=_queue_callback(queue))

    # 4. Signal completion and wait for renderer
    await queue.put(None)
    await renderer

    # 5. Print final result
    print(result.output)
```

### Render Loop

```python
async def _render_loop(queue, backend):
    await backend.start()
    try:
        while True:
            payload = await queue.get()
            if payload is None:
                break
            if isinstance(payload, CLIEvent):
                backend.handle_event(payload)
            queue.task_done()
    finally:
        await backend.stop()
```

## Approval Flow

### Interactive (TUI)

1. Worker calls tool requiring approval
2. Approval callback queues `CLIEvent(kind="approval_request", payload=request)`
3. TUI displays `ApprovalMessage` widget
4. User presses key (a/s/d/q)
5. Action handler queues `ApprovalDecision` to `approval_response_queue`
6. Worker receives decision, continues or aborts

### Non-Interactive

Requires `--approve-all` or `--strict` flag:
- `--approve-all`: All tools auto-approved
- `--strict`: All non-pre-approved tools rejected

## File Structure

```
llm_do/ui/
├── __init__.py          # Public exports
├── display.py           # DisplayBackend and implementations
├── app.py               # LlmDoApp Textual application
└── widgets/
    └── messages.py      # Message widget classes
```

## Dependencies

- **textual** - TUI framework
- **rich** - Terminal formatting
- **pydantic-ai** - Event types
- **pydantic-ai-blocking-approval** - Approval types

## CLI Flags Reference

| Flag | Effect |
|------|--------|
| (default) | TUI mode, captures to Rich buffer, prints on exit |
| `--headless` | Plain text output to stderr |
| `--rich` | Rich formatted output (with `--headless` or auto-detected non-TTY) |
| `--json` | JSONL output to stderr, JSON result to stdout |
| `--approve-all` | Auto-approve all tools (required for non-interactive) |
| `--strict` | Reject all non-pre-approved tools (required for non-interactive) |
