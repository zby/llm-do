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
            └── llm-do workers (sandboxed, delegatable)
```

## What llm-do Adds to TunaCode

1. **Declarative task definitions** (`.worker` YAML files)
2. **Sandboxed file operations** (per-worker path constraints)
3. **Worker delegation** (workers can call other workers)
4. **Pluggable toolsets** (filesystem, shell, delegation, custom)
5. **Program structure** (multi-worker projects with `program.yaml`)

## Implementation

### Registry + Approval Controller

Both projects use pydantic-ai. For integration, prefer `run_worker_async` with a
shared `WorkerRegistry` and `ApprovalController`. llm-do already exposes
`run_worker_async` and `WorkerRegistry` at the package level.

If you want live UI updates in TunaCode, reuse llm-do's event parsing layer:
`message_callback` -> `parse_event` -> `UIEvent`, then render into TunaCode's UI.

```python
# tunacode/integrations/llm_do_bridge.py (concept)
from pathlib import Path
from typing import Awaitable, Callable

from llm_do import WorkerRegistry, run_worker_async
from llm_do.ui.events import UIEvent
from llm_do.ui.parser import parse_event
from pydantic_ai_blocking_approval import ApprovalController, ApprovalDecision, ApprovalRequest

_bridge: "LlmDoBridge | None" = None

class LlmDoBridge:
    def __init__(
        self,
        registry_path: Path,
        approval_callback: Callable[[ApprovalRequest], Awaitable[ApprovalDecision]] | None = None,
        on_event: Callable[[UIEvent], None] | None = None,
    ) -> None:
        self.registry = WorkerRegistry(registry_path)
        self.approval_controller = ApprovalController(
            mode="interactive" if approval_callback else "approve_all",
            approval_callback=approval_callback,
        )
        self.on_event = on_event  # Optional hook for streaming UI updates

    def _message_callback(self, raw_events: list[object]) -> None:
        if not self.on_event:
            return
        for raw_event in raw_events:
            ui_event = parse_event(raw_event)
            self.on_event(ui_event)

    async def run(self, worker_name: str, task: str) -> str:
        result = await run_worker_async(
            registry=self.registry,
            worker=worker_name,
            input_data=task,
            approval_controller=self.approval_controller,
            message_callback=self._message_callback if self.on_event else None,
        )
        return str(result.output)

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
    """Delegate a task to an llm-do worker.

    Workers are defined in .worker YAML files and can:
    - Have sandboxed file access
    - Call other workers
    - Use custom toolsets
    """
    bridge = get_bridge()
    return await bridge.run(worker_name, task)
```

### TunaCode Startup

```python
# Initialize once per session (store in a module-level singleton or app state)
init_bridge(
    registry_path=Path("."),
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

The worker runs with its own sandbox constraints, can delegate to sub-workers, and approval requests flow through TunaCode's UI.

## Open Questions
- Is TunaCode's tool registration API stable enough for an external integration?
- Do we need streaming progress callbacks or is final output enough?
