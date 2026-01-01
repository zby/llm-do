# Integrating llm-do Workers into TunaCode

## Why This Direction?

| Direction | Effort | Result |
|-----------|--------|--------|
| **llm-do → TunaCode** | Add 1 tool + init call | Full TUI with slash commands, sessions, themes + llm-do workers |
| **TunaCode → llm-do** | Rebuild slash commands, sessions, themes... | Duplicating work |

TunaCode is a **rich interactive shell**. llm-do is a **worker execution engine**. They complement each other:

```
TunaCode (UI layer)
    └── call_llm_do_worker tool
            └── llm-do workers (delegatable)
```

## What llm-do Adds to TunaCode

1. **Declarative task definitions** (`.worker` YAML files)
2. **Toolset policies + approvals** (filesystem/shell approval gates)
3. **Worker delegation** (workers can call other workers)
4. **Pluggable toolsets** (filesystem, shell, custom)
5. **Context runtime** (nested calls, depth tracking, usage accounting)

## Implementation

### Context Runtime + Event Parsing

Both projects use pydantic-ai. For integration, reuse the runtime helper used
by the CLI. It loads worker/tool files, wraps approvals, and runs the entry in a
`Context`.

For live UI updates in TunaCode, reuse llm-do's event parsing layer:
`on_event` -> `parse_event` -> `UIEvent`, then render into TunaCode's UI.

```python
# tunacode/integrations/llm_do_bridge.py (concept)
from typing import Awaitable, Callable

from llm_do.runtime import ApprovalPolicy, run_entry
from llm_do.runtime.cli import build_entry
from llm_do.ui.events import UIEvent
from llm_do.ui.parser import parse_event
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalRequest

_bridge: "LlmDoBridge | None" = None

class LlmDoBridge:
    def __init(
        self,
        files: list[str],
        entry: str | None = None,
        model: str | None = None,
        approval_callback: Callable[[ApprovalRequest], Awaitable[ApprovalDecision]] | None = None,
        on_event: Callable[[UIEvent], None] | None = None,
    ) -> None:
        self.files = files
        self.entry = entry
        self.model = model
        self.on_event = on_event
        self.approval_callback = approval_callback

    def _on_event(self, ui_event: UIEvent) -> None:
        if self.on_event:
            self.on_event(ui_event)

    async def run(self, worker_name: str, task: str) -> str:
        worker_files = [f for f in self.files if f.endswith(".worker")]
        python_files = [f for f in self.files if f.endswith(".py")]
        entry = await build_entry(
            worker_files,
            python_files,
            model=self.model,
            entry_name=worker_name,
            set_overrides=None,
        )
        approval_policy = ApprovalPolicy(
            mode="approve_all" if self.approval_callback is None else "prompt",
            approval_callback=self.approval_callback,
        )
        result, _ctx = await run_entry(
            entry=entry,
            prompt=task,
            model=self.model,
            approval_policy=approval_policy,
            on_event=self._on_event if self.on_event else None,
        )
        return str(result)

def init_bridge(*args, **kwargs) -> None:
    global _bridge
    _bridge = LlmDoBridge(*args, **kwargs)

def get_bridge() -> "LlmDoBridge":
    if _bridge is None:
        raise RuntimeError("Call init_bridge() first")
    return _bridge
```

### TunaCode Tool

```python
# tunacode/tools/llm_do_worker.py
from tunacode.integrations.llm_do_bridge import get_bridge
from pydantic_ai.tools import RunContext

async def call_llm_do_worker(
    ctx: RunContext[None],
    worker_name: str,
    task: str,
) -> str:
    """Delegate a task to an llm-do worker."""
    bridge = get_bridge()
    return await bridge.run(worker_name, task)
```

### TunaCode Startup

```python
# Initialize once per session (store in a module-level singleton or app state)
init_bridge(
    files=["main.worker", "tools.py"],
    entry="main",
    approval_callback=tunacode_approval_handler,  # Bridge to TunaCode UI
    on_event=tunacode_render_event,               # Optional streaming display
)

# Register the tool with the agent (bridge in closure or global)
tools_list.append(Tool(call_llm_do_worker))
```

## Tracking

Work tracking lives in `docs/tasks/backlog/tunacode-integration.md`.

## Usage Example

Once integrated, TunaCode users can:

```
You: Analyze the authentication module for security issues

TunaCode: I'll delegate this to the security_analyzer worker.
[Calling llm-do worker: security_analyzer]
...
```

The worker can delegate to sub-workers, and approval requests flow through TunaCode's UI.

## Open Questions
- Is TunaCode's tool registration API stable enough for an external integration?
- Do we need streaming progress callbacks or is final output enough?
