# Toolset Plugin Architecture

## Overview

This document describes the toolset architecture in llm-do:
1. Workers declare toolsets via typed Pydantic config (`ToolsetsConfig`)
2. Toolsets receive config + specific dependencies they need
3. `ApprovalToolset` wrapper provides unified approval handling
4. Support for custom tools via `tools.py` files

## Current Architecture

Toolsets are built inline in `execution.py` (`prepare_agent_execution()`):

```python
# execution.py - builds toolsets from typed config
if shell_config is not None:
    shell_toolset = ShellToolset(
        config=shell_config.model_dump(),
        sandbox=context.sandbox,
    )
    approved = ApprovalToolset(
        inner=shell_toolset,
        approval_callback=context.approval_controller.approval_callback,
        memory=context.approval_controller.memory,
    )
    toolsets.append(approved)

if delegation_config is not None:
    delegation_toolset = DelegationToolset(
        config=delegation_config.model_dump(),
    )
    approved = ApprovalToolset(...)
    toolsets.append(approved)
```

### Design Principle: Keep pydantic-ai-blocking-approval Generic

The `pydantic-ai-blocking-approval` library provides a unified `ApprovalToolset` that:
- Auto-detects if inner toolset implements `SupportsNeedsApproval` protocol
- If yes: delegates approval decision to `inner.needs_approval()`
- If no: uses config dict to determine pre-approved tools (secure by default)

All toolset-specific logic lives in llm-do.

### Worker Configuration

Workers use typed Pydantic config for toolsets:

```yaml
# worker.yaml
toolsets:
  sandbox:
    paths:
      data: {mode: rw}
  shell:
    rules:
      - pattern: "git *"
        approval_required: false
    default:
      approval_required: true
  delegation:
    allow_workers: ["helper", "analyzer"]
  custom:
    my_tool: {pre_approved: false}
```

### Toolset Patterns

Two patterns for accessing runtime dependencies:

#### Pattern 1: Constructor injection (for external/generic toolsets)

Toolsets declare deps in `__init__` signature. Loader introspects and passes what's available.

```python
# pydantic_ai_filesystem_sandbox - external package, doesn't know WorkerContext
class FileSystemToolset(AbstractToolset):
    """Generic toolset - gets sandbox via constructor."""

    def __init__(self, sandbox: AbstractToolset):
        self._sandbox = sandbox

# Config-only external toolset
class DatabaseToolset(AbstractToolset):
    """No runtime deps needed."""

    def __init__(self, config: dict):
        self.connection_string = config["connection_string"]
```

#### Pattern 2: Runtime access via `ctx.deps` (for llm-do toolsets)

llm-do toolsets can access full `WorkerContext` at call time.

```python
# llm_do/delegation_toolset.py
class DelegationToolset(AbstractToolset[WorkerContext]):
    """Needs full context for worker orchestration."""

    def __init__(self, config: dict):
        self._config = config

    async def call_tool(self, name, tool_args, ctx, tool):
        from .runtime import call_worker_async, create_worker
        worker_ctx: WorkerContext = ctx.deps
        result = await call_worker_async(
            registry=worker_ctx.registry,
            worker=tool_args["worker"],
            ...
        )
```

#### Common: `needs_approval()` method

All toolsets can implement `needs_approval()` for smart approval logic:

```python
def needs_approval(self, name: str, tool_args: dict, ctx: RunContext) -> bool | dict:
    """Return False (pre-approved), True, or {"description": "..."}

    Args:
        name: Tool name being called
        tool_args: Arguments passed to the tool
        ctx: RunContext with deps (access via ctx.deps)
    """
```

The `ApprovalToolset` wrapper auto-detects via `SupportsNeedsApproval` protocol:
- If present → delegates to `inner.needs_approval()`
- If absent → uses `_approval_config` dict for `pre_approved` check (secure by default)

### WorkerContext as Dependency Container

`WorkerContext` serves as a runtime context container (not dependency injection):

```python
@dataclass
class WorkerContext:
    # Core references
    registry: WorkerRegistry          # For delegation lookups
    worker: WorkerDefinition          # Current worker definition
    approval_controller: ApprovalController
    creation_defaults: WorkerCreationDefaults

    # Optional runtime state
    sandbox: Optional[AbstractToolset] = None  # FileSystemToolset sandbox
    attachment_validator: Optional[AttachmentValidator] = None
    custom_tools_path: Optional[Path] = None
    effective_model: Optional[ModelLike] = None
    message_callback: Optional[MessageCallback] = None

    # Accumulator for attachments during execution
    attachments: List[AttachmentPayload] = field(default_factory=list)
```

Note: Delegation doesn't use injected protocols. Instead, `DelegationToolset.call_tool()`
imports runtime functions directly (`from .runtime import call_worker_async, create_worker`),
accessing `registry` and `creation_defaults` via `ctx.deps`.

## Benefits

1. **Unified approval handling**: `ApprovalToolset` wraps all toolsets uniformly
2. **Smart approval logic**: Toolsets implement `needs_approval()` for context-aware decisions
3. **No protocol overhead**: Delegation imports runtime functions directly (simpler than DI)
4. **Typed config**: `ToolsetsConfig` with Pydantic models for validation
5. **Testable**: Easy to mock context for testing toolsets

## Default Toolsets

Workers inherit defaults from `WorkerCreationDefaults`:

```python
class WorkerCreationDefaults(BaseModel):
    default_model: Optional[str] = None
    default_toolsets: Optional[ToolsetsConfig] = None
    default_attachment_policy: AttachmentPolicy = Field(default_factory=AttachmentPolicy)

    def expand_spec(self, spec: WorkerSpec) -> WorkerDefinition:
        """Apply defaults to a WorkerSpec to create a full definition."""
        ...
```

## Proposed: Plugin Architecture with Dynamic Loading

The goal is to decouple `execution.py` from specific toolset implementations, enabling:
- Dynamic loading of toolsets (including third-party)
- Workers declare toolsets by fully-qualified class name
- Single factory handles all toolset instantiation

### Worker Configuration (Proposed)

Workers would declare toolsets by fully-qualified class name:

```yaml
# worker.yaml
toolsets:
  # llm-do convention toolset (has needs_approval for smart approval logic)
  llm_do.toolsets.shell.ShellToolset:
    rules:
      - pattern: "git *"
        approval_required: false
    default:
      approval_required: true

  # llm-do convention toolset
  llm_do.toolsets.delegation.DelegationToolset:
    allow_workers: ["helper", "analyzer"]

  # Third-party toolset following llm-do convention (has needs_approval)
  mycompany.toolsets.DatabaseToolset:
    connection_string: "postgres://..."

  # Arbitrary pydantic-ai toolset (no needs_approval - uses config-based approval)
  some_library.SomeToolset:
    some_option: value
    _approval_config:
      some_tool: {pre_approved: true}
```

### Toolset Loader (Proposed)

Factory with signature introspection - passes runtime deps that toolsets declare in their `__init__`:

```python
# llm_do/toolset_loader.py
import importlib
import inspect
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import ApprovalToolset

def _import_class(class_path: str) -> type:
    """Dynamically import a class from its fully-qualified path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

def create_toolset(
    class_path: str,
    config: dict,
    context: "WorkerContext",
    approval_callback,
    memory,
) -> AbstractToolset:
    """Factory to create toolsets from config.

    Toolsets declare dependencies via __init__ signature:
    - __init__(config) -> config only, may use ctx.deps at runtime
    - __init__(config, sandbox) -> gets sandbox injected
    - __init__(config, sandbox, other_dep) -> extensible for future deps
    """
    toolset_class = _import_class(class_path)
    config = dict(config)  # copy to avoid mutation

    # Extract approval config (for toolsets without needs_approval)
    approval_config = config.pop("_approval_config", {})

    # Available runtime deps - extend as needed
    available_deps = {
        "sandbox": context.sandbox,
        # Future: "http_client": context.http_client, etc.
    }

    # Check what the constructor accepts
    sig = inspect.signature(toolset_class.__init__)
    kwargs = {"config": config}
    for dep_name, dep_value in available_deps.items():
        if dep_name in sig.parameters:
            kwargs[dep_name] = dep_value

    toolset = toolset_class(**kwargs)

    # Wrap with ApprovalToolset - it auto-detects needs_approval
    return ApprovalToolset(
        inner=toolset,
        approval_callback=approval_callback,
        memory=memory,
        config=approval_config,
    )


def build_toolsets(
    definition: "WorkerDefinition",
    context: "WorkerContext",
) -> list[AbstractToolset]:
    """Build all toolsets from worker definition."""
    toolsets = []
    for class_path, toolset_config in definition.toolsets.items():
        toolset = create_toolset(
            class_path=class_path,
            config=toolset_config,
            context=context,
            approval_callback=context.approval_controller.approval_callback,
            memory=context.approval_controller.memory,
        )
        toolsets.append(toolset)
    return toolsets
```

### Third-Party Toolset Examples

#### Following llm-do Convention

```python
# mycompany/toolsets/database.py
from pydantic_ai.toolsets import AbstractToolset
from llm_do.types import WorkerContext

class DatabaseToolset(AbstractToolset[WorkerContext]):
    """Database toolset with approval logic."""

    def __init__(self, config: dict):
        self.connection_string = config["connection_string"]
        self.readonly = config.get("readonly", True)

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        sql = tool_args.get("sql", "")
        if name == "query" and sql.lower().startswith("select"):
            return False  # Safe reads pre-approved
        return {"description": f"SQL: {sql[:60]}..."}

    async def get_tools(self, ctx):
        return {
            "query": ToolsetTool(...),
            "execute": ToolsetTool(...),
        }

    async def call_tool(self, name, tool_args, ctx, tool):
        # Access runtime deps via ctx.deps if needed
        # sandbox = ctx.deps.sandbox
        # registry = ctx.deps.registry
        # ... implementation using self.connection_string
```

Usage:
```yaml
toolsets:
  mycompany.toolsets.database.DatabaseToolset:
    connection_string: "${DATABASE_URL}"
    readonly: true
```

#### Toolset Needing Sandbox Access

```python
# mycompany/toolsets/file_processor.py
class FileProcessorToolset(AbstractToolset[WorkerContext]):
    """Third-party toolset that needs sandbox access."""

    def __init__(self, config: dict):
        self._extensions = config.get("extensions", [".txt", ".md"])

    async def call_tool(self, name, tool_args, ctx, tool):
        sandbox = ctx.deps.sandbox  # Access sandbox at runtime
        # ... process files in sandbox
```

#### Using Arbitrary pydantic-ai Toolset

For toolsets not designed for llm-do (no `ctx.deps` access), use `_approval_config`:

```yaml
toolsets:
  some_library.SomeToolset:
    some_option: value
    _approval_config:
      tool_a: {pre_approved: true}
      tool_b: {pre_approved: false}
```

## Migration Path

- [x] Unified `ApprovalToolset` with `SupportsNeedsApproval` protocol auto-detection
- [x] `WorkerContext` simplified (delegation uses runtime imports, not injected protocols)
- [x] Built-in toolsets implement `needs_approval()` for smart approval
- [x] DelegationToolset uses `ctx.deps` pattern for runtime access
- [ ] Create `llm_do/toolset_loader.py` with `build_toolsets()` factory
- [ ] Update `WorkerDefinition.toolsets` to use class paths as keys (Dict[str, Any])
- [ ] Replace hardcoded toolset creation in `execution.py` with `build_toolsets()`
- [ ] Support aliases for built-ins (`shell` → `llm_do.shell.toolset.ShellToolset`)
- [ ] Add backward compatibility layer for typed config format (optional)

## Open Questions

1. **Validation**: How to validate config before passing to toolset? Start simple (let it fail at runtime), add Pydantic config models later if needed.
2. **Aliases**: Support short names like `shell` -> `llm_do.shell.toolset.ShellToolset`? Hardcoded dict for built-ins is sufficient.

Note: Security for loading toolset classes is not a concern - users control their YAML config. The security boundary is the approval system for LLM-proposed tool calls at runtime.
