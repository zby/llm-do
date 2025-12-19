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

### Context Access

Both projects use pydantic-ai. llm-do uses `RunContext[WorkerContext]` for dependency injection; TunaCode uses `RunContext[None]` with a global `StateManager` singleton.

llm-do exposes a global singleton for external integrations:

```python
# llm_do/integrations/global_context.py
from llm_do import WorkerContext, WorkerRegistry, ApprovalController

class GlobalWorkerContext:
    """Global singleton for llm-do context in external integrations."""
    _instance: WorkerContext | None = None

    @classmethod
    def init(cls, registry_path: Path, approval_callback=None) -> None:
        cls._instance = WorkerContext(
            worker=None,  # Set per-call
            effective_model=None,  # Use worker's configured model
            approval_controller=ApprovalController(
                mode="interactive" if approval_callback else "approve_all",
                approval_callback=approval_callback,
            ),
            registry=WorkerRegistry(registry_path),
        )

    @classmethod
    def get(cls) -> WorkerContext:
        if cls._instance is None:
            raise RuntimeError("Call GlobalWorkerContext.init() first")
        return cls._instance
```

### TunaCode Tool

```python
# tunacode/tools/llm_do_worker.py
from llm_do.integrations import GlobalWorkerContext
from llm_do import call_worker_async
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
    worker_ctx = GlobalWorkerContext.get()
    result = await call_worker_async(
        registry=worker_ctx.registry,
        worker=worker_name,
        input_data=task,
        approval_controller=worker_ctx.approval_controller,
    )
    return str(result.output)
```

### TunaCode Startup

```python
from llm_do.integrations import GlobalWorkerContext

# Initialize with project root and optional approval bridge
GlobalWorkerContext.init(
    registry_path=Path("."),
    approval_callback=tunacode_approval_handler,  # Bridge to TunaCode UI
)

# Register the tool with the agent
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
