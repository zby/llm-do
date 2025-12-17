# TunaCode

Interactive TUI code agent with safe git branches, rich tools, and multi-LLM support.

## Quick Facts

| | |
|---|---|
| **Repository** | https://github.com/alchemiststudiosDOTai/tunacode |
| **Stars** | ~100 |
| **Primary use case** | Interactive chat-based code agent |
| **Python version** | 3.11–3.13 |
| **License** | MIT |
| **Activity** | Active development |

## Tech Stack

| Component | Library | Notes |
|-----------|---------|-------|
| **TUI framework** | Textual 4.x | Full TUI with NeXTSTEP-inspired design |
| **Terminal formatting** | Rich 14.x | Markdown rendering, syntax highlighting |
| **CLI framework** | typer 0.15+ / click 8.1.x | Entry point, argument parsing |
| **Input handling** | prompt_toolkit 3.x | Readline-style input, history |
| **Autocomplete** | textual-autocomplete 4.x | Command/path completion |
| **LLM integration** | pydantic-ai 1.x | Agent abstraction |
| **Data validation** | pydantic 2.12+ | Models, settings |
| **Syntax highlighting** | pygments 2.x | Code blocks |
| **Token counting** | tiktoken | Cost tracking |
| **Async** | asyncio | Throughout |

**Key observation:** Uses both Textual (for TUI) AND prompt_toolkit (for input). This is a common pattern - Textual for layout/widgets, prompt_toolkit for sophisticated readline.

## GUI Architecture

### Component Structure
```
tunacode/
├── ui/
│   ├── main.py           # Textual App entry point
│   ├── app.tcss          # Textual CSS styling
│   └── commands/         # Slash command handlers
│       └── __init__.py   # Command registry
├── core/
│   └── state.py          # SessionState singleton
├── tools/
│   ├── authorization/    # 7-file approval system
│   │   ├── context.py
│   │   ├── factory.py
│   │   ├── handler.py
│   │   ├── notifier.py
│   │   ├── policy.py
│   │   ├── requests.py
│   │   └── rules.py
│   └── bash.py           # Shell with security patterns
└── agents/
    └── research.py       # Read-only exploration agent
```

### State Management
**Pattern:** Global singleton (`SessionState`)

```python
@dataclass
class SessionState:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    current_model: str = ""
    messages: List[Message] = field(default_factory=list)
```

This is simpler than llm-do's context passing but doesn't support nested worker calls.

### Event System
Standard Textual message passing. No custom event bus documented.

### Streaming Responses
Uses pydantic-ai's streaming with Rich for rendering markdown chunks.

### Slash Commands
Registry pattern in `ui/commands/__init__.py`:

```python
COMMANDS = {
    "/help": {"handler": show_help, "description": "Show available commands"},
    "/clear": {"handler": clear_history, "description": "Clear conversation"},
    "/yolo": {"handler": toggle_yolo, "description": "Toggle auto-confirm"},
    "/model": {"handler": switch_model, "description": "Switch model"},
    "/branch": {"handler": create_branch, "description": "Create git branch"},
    "/plan": {"handler": toggle_plan, "description": "Read-only planning mode"},
    "/theme": {"handler": switch_theme, "description": "Switch theme"},
    "/resume": {"handler": resume_session, "description": "Resume previous session"},
}
```

Shell escape: `!<cmd>` executes shell command directly.

## Borrowable Patterns

### 1. Token/Cost Tracking
**Effort:** ~1 hour | **Value:** High

```python
# From tunacode/core/state.py
class SessionState:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def update_token_count(self, usage):
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
```

**For llm-do:** Add to `WorkerRunResult`. pydantic-ai already provides usage info.

### 2. Dangerous Command Patterns
**Effort:** ~30 min | **Value:** Security improvement

```python
# From tunacode/tools/bash.py
DANGEROUS_PATTERNS = ["rm -rf", "dd if=", "mkfs", ...]
SECURITY_PATTERNS = [
    r";rm", r"&&rm",      # Command chaining to rm
    r":\(\)\{.*\}",       # Fork bombs
]
```

**For llm-do:** Add to `ShellToolset` as default blocked patterns.

### 3. Output Truncation (head + tail)
**Effort:** ~30 min | **Value:** Better UX

```python
if len(output) > MAX_COMMAND_OUTPUT:
    head = output[:MAX_COMMAND_OUTPUT // 2]
    tail = output[-MAX_COMMAND_OUTPUT // 2:]
    output = f"{head}\n... truncated ...\n{tail}"
```

**For llm-do:** Improve shell output truncation.

### 4. Slash Commands Framework
**Effort:** ~1 day | **Value:** Medium

Registry pattern is clean. Would require making our TUI conversational.

### 5. Session Persistence
**Effort:** ~1 day | **Value:** Medium

```python
def save_session(self) -> None:
    data = {
        "messages": self._serialize_messages(),
        "model": self.session.current_model,
        "timestamp": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(data))
```

**For llm-do:** Would enable resuming interrupted workers.

## Integration Options

### Us → Them (embed llm-do workers into TunaCode)

**Approach:** Add `call_llm_do_worker` tool to TunaCode

```python
async def call_llm_do_worker(worker_name: str, task: str) -> str:
    """Delegate to an llm-do worker with sandboxed execution."""
    result = await call_worker_async(registry, worker_name, task)
    return str(result.output)
```

**Value:** TunaCode users get llm-do's sandboxing, delegation, and worker definitions.

See `tunacode-integration.md` for full implementation plan.

### Them → Us (borrow TunaCode components)

| Component | Feasibility | Notes |
|-----------|-------------|-------|
| Token tracking | Easy | Just add fields to WorkerRunResult |
| Bash security patterns | Easy | Add to ShellToolset |
| Slash commands | Medium | Need conversational TUI first |
| Theme system | Low priority | Nice-to-have |
| Authorization system | Skip | Our approval system is simpler and sufficient |

## Key Differences from llm-do

| Aspect | TunaCode | llm-do |
|--------|----------|--------|
| **Focus** | Interactive chat | Task execution |
| **State** | Global singleton | Context passing |
| **Workers** | Single agent | Multi-worker delegation |
| **Sandboxing** | None | Per-worker sandboxes |
| **Configuration** | JSON config file | YAML worker definitions |

## References

- Repository: https://github.com/alchemiststudiosDOTai/tunacode
- Website: https://tunacode.xyz
