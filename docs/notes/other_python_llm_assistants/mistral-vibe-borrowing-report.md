# Mistral Vibe Borrowing Report

Analysis of patterns and code to borrow from mistral-vibe for improving llm-do's TUI.

**Source:** `/home/zby/llm/mistral-vibe/`

---

## Executive Summary

Mistral-vibe has a mature, well-architected TUI built on Textual. Key findings:

1. **Streaming markdown** - Uses `MarkdownStream` for real-time LLM response rendering
2. **Modal approval flow** - Swaps bottom panel between input/approval modes with async Future blocking
3. **Tool-specific renderers** - Registry pattern for customizing approval/result display per tool
4. **Session-level approval** - "Always allow this tool" option for repetitive operations
5. **Animated states** - Blinking dots, gradient spinners, color-coded success/failure
6. **Smart input** - Prefix-based history search, multi-controller completion

**Priority borrowing order:**
1. Streaming markdown widget (critical)
2. Modal approval UI with tool renderers (high)
3. Blinking state indicators (medium)
4. Collapsible tool results (medium)
5. Enhanced input with history (medium)

---

## llm-do UI Architecture Context

- Raw worker events are parsed once in `llm_do/ui/parser.py` into `UIEvent`.
- `UIEvent` handles rendering for Rich, headless text, JSON, and Textual widgets.
- Textual TUI uses `LlmDoApp` + `MessageContainer` to mount message widgets.
- Approvals are surfaced as `ApprovalRequestEvent` and resolved via an approval queue.

## Phase 1 Analysis Results

### 1. TUI App Structure

**File:** `vibe/cli/textual_ui/app.py` (1134 lines)

#### Key Architectural Patterns

**Bottom Panel Switching:**
```python
class BottomApp(StrEnum):
    Approval = auto()
    Config = auto()
    Input = auto()

async def _switch_to_approval_app(self, tool_name: str, tool_args: dict) -> None:
    bottom_container = self.query_one("#bottom-app-container")
    await chat_input_container.remove()
    approval_app = ApprovalApp(tool_name=tool_name, tool_args=tool_args)
    await bottom_container.mount(approval_app)
    self._current_bottom_app = BottomApp.Approval
```

**Event Handler Separation:**
```python
class EventHandler:
    async def handle_event(self, event: BaseEvent, ...) -> ToolCallMessage | None:
        match event:
            case ToolCallEvent():
                return await self._handle_tool_call(event, loading_widget)
            case ToolResultEvent():
                await self._handle_tool_result(event)
            case AssistantEvent():
                await self._handle_assistant_message(event)
```

**Async Approval Callback:**
```python
async def _approval_callback(self, tool: str, args: dict, tool_call_id: str):
    self._pending_approval = asyncio.Future()
    await self._switch_to_approval_app(tool, args)
    result = await self._pending_approval  # Blocks until user responds
    return result
```

**Smart Auto-Scroll:**
```python
async def _mount_and_scroll(self, widget: Widget) -> None:
    chat = self.query_one("#chat", VerticalScroll)
    was_at_bottom = self._is_scrolled_to_bottom(chat)
    if was_at_bottom:
        self._auto_scroll = True
    await messages_area.mount(widget)
    if was_at_bottom:
        self.call_after_refresh(self._anchor_if_scrollable)
```

#### Keyboard Bindings
```python
BINDINGS = [
    Binding("ctrl+c", "force_quit", "Quit", show=False),
    Binding("escape", "interrupt", "Interrupt", show=False, priority=True),
    Binding("ctrl+o", "toggle_tool", "Toggle Tool", show=False),
    Binding("shift+tab", "cycle_mode", "Cycle Mode", show=False, priority=True),
    Binding("shift+up", "scroll_chat_up", "Scroll Up", show=False, priority=True),
]
```

---

### 2. Widget Library

**Files:** `vibe/cli/textual_ui/widgets/` (~1900 lines)

#### Message Widgets

**Streaming AssistantMessage:**
```python
class AssistantMessage(Static):
    def _ensure_stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = Markdown.get_stream(self._get_markdown())
        return self._stream

    async def append_content(self, content: str) -> None:
        stream = self._ensure_stream()
        await stream.write(content)

    async def stop_stream(self) -> None:
        if self._stream:
            await self._stream.stop()
            self._stream = None
```

**BashOutputMessage with exit status:**
```python
def compose(self) -> ComposeResult:
    with Vertical(classes="bash-output-container"):
        with Horizontal(classes="bash-cwd-line"):
            yield Static(self._cwd, markup=False, classes="bash-cwd")
            if self._exit_code == 0:
                yield Static("✓", classes="bash-exit-success")
            else:
                yield Static("✗", classes="bash-exit-failure")
                yield Static(f" ({self._exit_code})", classes="bash-exit-code")
```

#### Tool Display Widgets

**BlinkingMessage for tool execution:**
```python
class BlinkingMessage(Static):
    def toggle_blink(self) -> None:
        self.blink_state = not self.blink_state
        dot = "● " if self.blink_state else "○ "
        self._dot_widget.update(dot)

    def stop_blinking(self, success: bool = True) -> None:
        self._is_blinking = False
        self._dot_widget.update("● ")
        if success:
            self._dot_widget.add_class("success")  # Green
        else:
            self._dot_widget.add_class("error")    # Red
```

**Collapsible ToolResultMessage:**
```python
async def render_result(self) -> None:
    await self.remove_children()
    if self.collapsed:
        self.update("Summary (ctrl+o to expand)")
    else:
        renderer = get_renderer(self.event.tool_name)
        widget_class, data = renderer.get_result_widget(display, self.collapsed)
        await self.mount(widget_class(data, collapsed=self.collapsed))
```

#### Loading Widget

**Gradient animation:**
```python
class LoadingWidget(Static):
    BRAILLE_SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    TARGET_COLORS = ("#FFD800", "#FFAF00", "#FF8205", "#FA500F", "#E10500")

    def update_animation(self) -> None:
        spinner_char = self.BRAILLE_SPINNER[self.spinner_pos]
        for i, widget in enumerate(self.char_widgets):
            color = self._get_gradient_color(2 + i)
            widget.update(f"[{color}]{self.status[i]}[/]")
        self.gradient_offset = (self.gradient_offset + 1) % len(self.TARGET_COLORS)
```

#### Input Widgets

**Multiline with history:**
```python
# Enter = submit, Shift+Enter = newline
BINDINGS = [
    Binding("shift+enter,ctrl+j", "insert_newline", "New Line", priority=True)
]

def _handle_history_up(self) -> bool:
    if cursor_row == 0:  # Only on first line
        if self._history_prefix is None:
            self._history_prefix = self._get_prefix_up_to_cursor()
        self.post_message(self.HistoryPrevious(self._history_prefix))
        return True
    return False
```

**Multi-controller completion:**
```python
class MultiCompletionManager:
    def on_text_changed(self, text: str, cursor_index: int) -> None:
        for controller in self._controllers:
            if controller.can_handle(text, cursor_index):
                candidate = controller
                break
        if candidate is not self._active:
            if self._active:
                self._active.reset()
            self._active = candidate
```

---

### 3. Approval UI

**Files:** `widgets/approval_app.py`, `renderers/tool_renderers.py`

#### Modal Approval Flow

```python
class ApprovalApp(Container):
    BINDINGS = [
        Binding("up", "move_up", "Up"),
        Binding("down", "move_down", "Down"),
        Binding("enter", "select", "Select"),
        Binding("1", "select_1", "Yes"),
        Binding("y", "select_1", "Yes"),
        Binding("2", "select_2", "Always Tool Session"),
        Binding("3", "select_3", "No"),
        Binding("n", "select_3", "No"),
    ]

    class ApprovalGranted(Message): ...
    class ApprovalGrantedAlwaysTool(Message): ...
    class ApprovalRejected(Message): ...
```

#### Tool-Specific Renderers

```python
_RENDERER_REGISTRY: dict[str, type[ToolRenderer]] = {
    "write_file": WriteFileRenderer,
    "search_replace": SearchReplaceRenderer,
    "bash": BashRenderer,
}

def get_renderer(tool_name: str) -> ToolRenderer:
    renderer_class = _RENDERER_REGISTRY.get(tool_name, ToolRenderer)
    return renderer_class()

# Usage
renderer = get_renderer(self.tool_name)
widget_class, data = renderer.get_approval_widget(self.tool_args)
```

#### Session-Level Approval

```python
case 1:  # Always Tool Session
    self.post_message(ApprovalGrantedAlwaysTool(
        tool_name, tool_args, save_permanently=False
    ))

# Handler updates in-memory config
def _set_tool_permission_always(self, tool_name: str, save_permanently: bool):
    self.config.tools[tool_name].permission = ToolPermission.ALWAYS
```

#### Color-Coded Options

```css
.approval-cursor-selected {
    &.approval-option-yes {
        color: $text-success;    /* Green */
        text-style: bold;
    }
    &.approval-option-no {
        color: $text-error;      /* Red */
        text-style: bold;
    }
}
```

---

## Recommendations for llm-do

### Critical (Must Have)

- [ ] **Streaming markdown widget** - Use `MarkdownStream` inside `AssistantMessage`/`MessageContainer`
- [ ] **Modal approval UI** - Implement in `LlmDoApp` with the existing approval queue
- [ ] **Tool-specific renderers** - Registry called from `UIEvent.create_widget` or `ToolResultMessage`

### High Priority

- [ ] **Session-level approval** - "Always allow this tool" option in `ApprovalController`
- [ ] **Blinking tool indicators** - Visual feedback in tool widgets
- [ ] **Collapsible results** - Toggle in `ToolResultMessage` (with a keybinding in `LlmDoApp`)

### Medium Priority

- [ ] **Smart auto-scroll** - Only scroll if user was at bottom (`MessageContainer`)
- [ ] **Loading animation** - Braille spinner widget for status events
- [ ] **Enhanced input** - Enable `LlmDoApp` input and add history/multiline
- [ ] **Color-coded approval options** - Update `ApprovalMessage`/CSS themes

### Nice to Have

- [ ] **Multi-controller completion** - Slash commands + path completion
- [ ] **Dangerous directory warnings** - Alert when running in system dirs
- [ ] **Tool-specific result widgets** - Bash output, diffs, file previews

---

## Files to Study Further

| File | Lines | Key Patterns |
|------|-------|--------------|
| `cli/textual_ui/app.py` | 1134 | Main app, approval flow, event loop |
| `cli/textual_ui/widgets/messages.py` | 148 | Streaming markdown |
| `cli/textual_ui/widgets/approval_app.py` | 197 | Modal approval UI |
| `cli/textual_ui/widgets/tool_widgets.py` | 307 | Tool result display |
| `cli/textual_ui/widgets/loading.py` | 157 | Animated loading |
| `cli/textual_ui/widgets/chat_input/` | ~400 | Input with history/completion |
| `cli/textual_ui/renderers/tool_renderers.py` | 220 | Tool-specific rendering |
| `cli/textual_ui/app.tcss` | 683 | CSS styling patterns |

---

## Architecture Compatibility Analysis

**Question:** Is mistral-vibe's architecture compatible with recursive workers (llm-do pattern)?

**Answer:** **No, it is not.** The architectures are fundamentally different.

### Mistral-Vibe Tool Architecture

```python
# base.py - Tool signature
class BaseTool[ToolArgs, ToolResult, ToolConfig, ToolState]:
    async def run(self, args: ToolArgs) -> ToolResult:
        """Only receives validated args - no runtime context."""
        ...

# How tools access resources:
async def run(self, args: ReadFileArgs) -> ReadFileResult:
    file_path = self.config.effective_workdir / args.file_path  # config only
    self.state.recently_read_files.append(str(file_path))       # state only
```

**Tools only have access to:**
- `self.config` - Static configuration (workdir, permissions, limits)
- `self.state` - Mutable tool state (recently_read_files, search_history)

**Tools do NOT have access to:**
- Agent instance
- Tool manager / registry
- Approval controller
- Other runtime services

### Why Recursive Workers Don't Work

In llm-do, tools receive `RunContext[CallContext]` via dependency injection:

```python
# llm-do pattern
from pydantic_ai.tools import RunContext
from llm_do.runtime import CallContext

async def create_file(ctx: RunContext[CallContext], file_path: str, content: str):
    # Can call other agents through context
    result = await ctx.deps.call_agent("validate_syntax", {"input": content})
    # Can access approvals, depth, usage via ctx.deps
```

In mistral-vibe, there's no equivalent:

```python
# mistral-vibe pattern - NO context injection
async def run(self, args: WriteFileArgs) -> WriteFileResult:
    # Cannot call other tools
    # Cannot access agent
    # Cannot spawn sub-agents
    file_path.write_text(args.content)  # Just do the work directly
```

### Execution Flow Comparison

**Mistral-Vibe (flat):**
```
Agent._conversation_loop()
  └─► LLM generates tool calls
      └─► Agent._handle_tool_calls()
          └─► tool_instance.invoke(**args)
              └─► tool.run(validated_args)  ← isolated execution
```

**llm-do (recursive):**
```
Context.run(entry)
  └─► WorkerEntry executes
      └─► ctx.deps.call("sub_worker", {"input": ...})  ← recursive call
          └─► Context resolves worker tool
              └─► Sub-worker executes
                  └─► ctx.deps.call(...)  ← deeper nesting possible
```

### What Would Be Needed

To add recursive tool support to mistral-vibe:

1. **Inject runtime context into tools:**
   ```python
   async def run(self, args: ToolArgs, context: RuntimeContext) -> ToolResult:
   ```

2. **Provide tool invocation capability:**
   ```python
   result = await context.invoke_tool("other_tool", **args)
   ```

3. **Handle approval recursively** (currently single-level)

4. **Manage nested conversation state**

This would be a significant refactor - essentially reimplementing llm-do's core pattern.

### Conclusion

**Borrow the TUI, not the tool architecture.**

- ✅ TUI widgets - Excellent patterns for streaming, approval, animation
- ✅ CSS styling - Professional look, color schemes
- ✅ Event handling - Clean separation of concerns
- ❌ Tool system - Not compatible with recursive workers
- ❌ Agent architecture - Single-level, not composable

---

## Phase 2 Analysis Results

### 4. Textual CSS Styling

**File:** `vibe/cli/textual_ui/app.tcss` (~683 lines)

#### Key Styling Patterns

**Opacity-based backgrounds (instead of darken variants):**
```css
.tool-result {
    background: $surface;

    &.error-text {
        background: $error 10%;  /* 10% opacity overlay */
        color: $text-error;
    }

    &.warning-text {
        background: $warning 10%;
        color: $text-warning;
    }
}
```

**State-based message styling:**
```css
.user-message {
    &.pending {
        .user-message-prompt,
        .user-message-content {
            opacity: 0.7;
            text-style: italic;
        }
    }
}
```

**Structured bash output display:**
```css
.bash-cwd-line {
    width: 100%;
    align: left middle;
}

.bash-cwd { color: $text-muted; }
.bash-chevron { color: $primary; text-style: bold; }
.bash-exit-success { color: $text-success; }
.bash-exit-failure { color: $text-error; }
```

**Approval UI uses warning (yellow), not error (red):**
```css
.approval-title {
    color: $warning;  /* Decision points, not errors */
    text-style: bold;
}
```

#### CSS Recommendations for llm-do

**Quick wins:**
1. Replace `$warning-darken-3` with `$warning 15%` (opacity-based)
2. Change approval UI from `$error` to `$warning` theme
3. Add markdown overflow handling:
   ```css
   Markdown MarkdownFence {
       overflow-x: auto;
       max-width: 95%;
   }
   ```

**Visual hierarchy:**
- Tool names in `$primary` or `$warning`
- Success indicators in `$text-success`
- Timestamps/metadata in `$text-muted`

---

### 5. Tool System Security Patterns

**Files:** `core/tools/manager.py`, `core/tools/builtins/bash.py`

#### Multi-Layered Permission System

```python
class ToolPermission(StrEnum):
    ALWAYS = auto()  # Auto-execute
    NEVER = auto()   # Block entirely
    ASK = auto()     # Prompt user
```

**Permission check flow:**
1. Check auto-approve flag
2. Check tool-specific allowlist/denylist patterns
3. Check base permission level
4. Ask user for approval

#### Dangerous Command Detection (Worth Borrowing)

**Three-tier filtering for bash:**

```python
# 1. Allowlist - auto-approve safe commands
allowlist = ["echo", "cat", "ls", "pwd", "git status", "git diff", "git log"]

# 2. Denylist - block dangerous patterns
denylist = ["vim", "nano", "emacs", "bash -i", "python"]  # Interactive

# 3. Standalone denylist - block bare commands but allow with args
denylist_standalone = ["python", "bash", "sh"]  # "python" blocked, "python script.py" OK
```

**Pattern matching splits on shell operators:**
```python
command_parts = re.split(r"(?:&&|\|\||;|\|)", args.command)
# Checks each part independently
```

#### Environment Stabilizing

```python
env = {
    **os.environ,
    "CI": "true",
    "NONINTERACTIVE": "1",
    "GIT_PAGER": "cat",  # Prevent less/more
    "PAGER": "cat",
    "DEBIAN_FRONTEND": "noninteractive",
}
```

#### Key Security Patterns for llm-do

- **Dangerous command detection** - Split on `&&`, `||`, `;`, `|` and check each part
- **Standalone vs with-args** - `python` alone is dangerous, `python script.py` is OK
- **Environment stabilizing** - Prevent interactive prompts
- **Process tree termination** - Kill entire process group on timeout

---

### 6. Event Handling Architecture

**Files:** `handlers/event_handler.py`, `core/middleware.py`

#### Generator-Based Event Streaming

```python
# Agent yields typed events
async def act(self, msg: str) -> AsyncGenerator[BaseEvent]:
    async for event in self._conversation_loop(msg):
        yield event

# UI consumes in simple loop
async for event in self.agent.act(prompt):
    await self.event_handler.handle_event(event)
```

#### Event Types

```python
class AssistantEvent(BaseEvent):
    content: str

class ToolCallEvent(BaseEvent):
    tool_name: str
    args: BaseModel
    tool_call_id: str

class ToolResultEvent(BaseEvent):
    tool_name: str
    result: BaseModel | None
    error: str | None
    duration: float | None
```

#### Pattern Matching Dispatch

```python
async def handle_event(self, event: BaseEvent) -> None:
    match event:
        case ToolCallEvent():
            return await self._handle_tool_call(event)
        case ToolResultEvent():
            await self._handle_tool_result(event)
        case AssistantEvent():
            await self._handle_assistant_message(event)
```

#### Middleware Pipeline

```python
class ConversationMiddleware(Protocol):
    async def before_turn(self, ctx: ConversationContext) -> MiddlewareResult
    async def after_turn(self, ctx: ConversationContext) -> MiddlewareResult

class MiddlewareAction(StrEnum):
    CONTINUE = auto()
    STOP = auto()           # Terminate conversation
    COMPACT = auto()        # Trigger summarization
    INJECT_MESSAGE = auto() # Add system message
```

**Built-in middlewares:**
- `TurnLimitMiddleware` - Prevent infinite loops
- `PriceLimitMiddleware` - Cost control
- `AutoCompactMiddleware` - Auto-summarize on context limit
- `ContextWarningMiddleware` - Warn at 50% context usage

#### Event Handling Recommendations for llm-do

1. **Single parse point** - Keep event discrimination in `llm_do/ui/parser.py`
2. **Typed event hierarchy** - Extend `UIEvent` for new UI features
3. **Pattern matching dispatch** - Already in `parse_event` and `MessageContainer.handle_event`
4. **Paired events** - ToolCallEvent → ToolResultEvent for progress tracking
5. **Middleware pipeline** - Keep in agent runner layer, not in the UI

---

## Summary: What to Borrow

### Critical (Immediate Value)

| Pattern | Source | Benefit |
|---------|--------|---------|
| Streaming markdown | `MarkdownStream` | Real-time LLM responses |
| Modal approval UI | `approval_app.py` | Better UX for confirmations |
| Dangerous cmd detection | `bash.py` | Prevent hangs/destruction |

### High Priority

| Pattern | Source | Benefit |
|---------|--------|---------|
| Opacity-based CSS | `app.tcss` | Professional look |
| Blinking indicators | `BlinkingMessage` | Visual feedback |
| Environment stabilizing | `bash.py` | Prevent interactive prompts |

### Medium Priority

| Pattern | Source | Benefit |
|---------|--------|---------|
| UIEvent adapters | `agent.py` | Feed generator events into `UIEvent` pipeline |
| Middleware pipeline | `middleware.py` | Composable guards |
| Tool renderer registry | `renderers/tool_renderers.py` | Per-tool widgets via `UIEvent.create_widget` |

### Not Applicable

| Pattern | Reason |
|---------|--------|
| Tool architecture | No recursive workers |
| Agent class | Single-level only |
| MCP integration | Different approach |

## Open Questions
- Which two or three TUI improvements should be prioritized first for llm-do?
- Do we want to prototype the modal approval flow before streaming markdown?
