# Toolset Plugin Architecture

## Overview

This document proposes a plugin architecture for toolsets in llm-do, enabling:
1. Workers to declare which toolsets they use by class name
2. Dynamic loading of toolsets (including third-party)
3. Clean dependency injection via WorkerContext
4. Support for both llm-do convention toolsets and arbitrary pydantic-ai toolsets

## Current State

Currently, toolsets are hardcoded in `execution.py`:

```python
# execution.py - knows about each specific toolset
if shell_config is not None:
    shell_toolset = ShellApprovalToolset(
        config=shell_config.model_dump(),
        sandbox=context.sandbox,
        approval_callback=...,
        memory=...,
    )
    toolsets.append(shell_toolset)

if delegation_config is not None:
    delegation_toolset = DelegationApprovalToolset(
        config=delegation_config.model_dump(),
        delegator=delegator,
        creator=creator,
        ...
    )
```

Problems:
- `execution.py` is coupled to every toolset implementation
- Each ApprovalToolset subclass reimplements `__init__`
- Adding new toolsets requires modifying `execution.py`
- No support for third-party toolsets

## Proposed Architecture

### Design Principle: Keep pydantic-ai-blocking-approval Generic

The `pydantic-ai-blocking-approval` library should remain a generic approval wrapper with no llm-do-specific conventions. All plugin/factory logic lives in llm-do.

### Worker Configuration

Workers declare toolsets by fully-qualified class name:

```yaml
# worker.yaml
toolsets:
  llm_do.toolsets.shell.ShellToolset:
    rules:
      - pattern: "git *"
        approval_required: false
    default:
      allowed: true
      approval_required: true

  llm_do.toolsets.delegation.DelegationToolset:
    allow_workers: ["helper", "analyzer"]

  # Third-party toolset following llm-do convention
  mycompany.toolsets.DatabaseToolset:
    connection_string: "postgres://..."

  # Arbitrary pydantic-ai toolset (wrapped automatically)
  some_library.SomeToolset:
    _approval: default  # use SimpleApprovalToolset wrapper
    some_option: value
```

### Toolset Loader in llm-do

The factory logic lives entirely in llm-do:

```python
# llm_do/toolset_loader.py
import importlib
from typing import Any, Callable, Optional
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import ApprovalToolset, SimpleApprovalToolset, ApprovalMemory

def _import_class(class_path: str) -> type:
    """Dynamically import a class from its fully-qualified path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

def create_toolset(
    class_path: str,
    config: dict,
    context: "WorkerContext",
    approval_callback: Callable,
    memory: ApprovalMemory,
) -> AbstractToolset:
    """Factory to create toolsets from config.

    Supports three patterns:
    1. llm-do convention: class has `inner_class` attribute, inner follows (config, context)
    2. llm-do simple: class itself follows (config, context) convention
    3. Arbitrary pydantic-ai: wrap with SimpleApprovalToolset
    """
    toolset_class = _import_class(class_path)
    config = dict(config)  # copy to avoid mutation

    # Pattern 1: ApprovalToolset subclass with inner_class attribute
    if hasattr(toolset_class, "inner_class"):
        inner_class = toolset_class.inner_class
        # Allow config override of inner class
        if "_inner_class" in config:
            inner_class = _import_class(config.pop("_inner_class"))
        inner = inner_class(config, context)
        return toolset_class(
            inner=inner,
            approval_callback=approval_callback,
            memory=memory,
            config=config,
        )

    # Pattern 2: Toolset follows (config, context) convention directly
    if _has_config_context_init(toolset_class):
        toolset = toolset_class(config, context)
        # If it has needs_approval, wrap with ApprovalToolset
        if hasattr(toolset, "needs_approval"):
            return ApprovalToolset(
                inner=toolset,
                approval_callback=approval_callback,
                memory=memory,
                config=config,
            )
        # Otherwise wrap with SimpleApprovalToolset
        return SimpleApprovalToolset(
            inner=toolset,
            approval_callback=approval_callback,
            memory=memory,
            config=config.get("_approval_config", {}),
        )

    # Pattern 3: Arbitrary pydantic-ai toolset
    # Extract approval config, pass rest to toolset
    approval_config = config.pop("_approval_config", {})
    toolset = toolset_class(**config)
    return SimpleApprovalToolset(
        inner=toolset,
        approval_callback=approval_callback,
        memory=memory,
        config=approval_config,
    )

def _has_config_context_init(cls: type) -> bool:
    """Check if class __init__ accepts (config, context) signature."""
    import inspect
    sig = inspect.signature(cls.__init__)
    params = list(sig.parameters.keys())
    # Expect: self, config, context
    return len(params) >= 3 and params[1] == "config" and params[2] == "context"

def build_toolsets(
    definition: "WorkerDefinition",
    context: "WorkerContext",
    approval_callback: Callable,
    memory: ApprovalMemory,
) -> list[AbstractToolset]:
    """Build all toolsets from worker definition."""
    toolsets = []
    for class_path, toolset_config in definition.toolsets.items():
        toolset = create_toolset(
            class_path=class_path,
            config=toolset_config,
            context=context,
            approval_callback=approval_callback,
            memory=memory,
        )
        toolsets.append(toolset)
    return toolsets
```

### llm-do Convention for Toolsets

Toolsets following the llm-do convention have:

1. **Inner class attribute**: Points to the core toolset implementation
2. **Inner class `(config, context)` signature**: Receives config dict and WorkerContext
3. **`needs_approval()` method**: On inner class for approval logic

```python
# llm_do/toolsets/shell.py
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import BaseApprovalToolset

class ShellToolsetInner(AbstractToolset):
    """Core shell command execution."""

    def __init__(self, config: dict, context: "WorkerContext"):
        self.sandbox = context.sandbox
        self.config = config

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        """Approval logic lives here, close to the implementation."""
        if name != "shell":
            return True
        command = tool_args.get("command", "")
        # ... pattern matching logic ...
        if not approval_required:
            return False
        return {"description": f"Execute: {command[:80]}"}

    async def get_tools(self, ctx) -> dict:
        # ... tool definitions

    async def call_tool(self, name, tool_args, ctx, tool) -> Any:
        # ... execution logic


class ShellToolset(BaseApprovalToolset):
    """Shell toolset with approval wrapper."""
    inner_class = ShellToolsetInner
```

### WorkerContext as Dependency Container

`WorkerContext` serves as a dependency injection container:

```python
@dataclass
class WorkerContext:
    # Core dependencies available to all toolsets
    registry: WorkerRegistry
    worker: WorkerDefinition
    approval_controller: ApprovalController

    # Optional dependencies (toolsets check for None)
    sandbox: Optional[FileSandbox] = None
    delegator: Optional[WorkerDelegator] = None
    creator: Optional[WorkerCreator] = None
    custom_tools_path: Optional[Path] = None

    # Runtime state
    attachments: List[AttachmentPayload] = field(default_factory=list)
    effective_model: Optional[ModelLike] = None
    message_callback: Optional[MessageCallback] = None
```

## Benefits

1. **Decoupled execution.py**: No toolset-specific code, just calls `build_toolsets()`
2. **pydantic-ai-blocking-approval stays generic**: No llm-do conventions leak into the library
3. **Third-party toolsets**: Follow convention or get auto-wrapped
4. **Arbitrary pydantic-ai toolsets**: Work out of the box with SimpleApprovalToolset wrapper
5. **Explicit DI**: Dependencies flow through WorkerContext
6. **Testable**: Easy to mock context for testing toolsets

## Migration Path

1. Create `llm_do/toolset_loader.py` with factory functions
2. Update inner toolsets to accept `(config, context)` and implement `needs_approval()`
3. Add `inner_class` attribute to approval wrapper classes
4. Update `WorkerDefinition.toolsets` to use class paths as keys
5. Replace hardcoded toolset creation in `execution.py` with `build_toolsets()`
6. Add backward compatibility layer for old config format (optional)

## Default Toolsets

Workers could specify defaults via a special key or inherit from a base:

```yaml
# Option A: Explicit defaults
toolsets:
  _defaults: [shell, delegation]  # Short aliases for built-ins
  llm_do.toolsets.shell.ShellToolset:
    rules: [...]

# Option B: Inherit from profile
extends: default_profile  # Includes standard toolsets
toolsets:
  # Additional or override toolsets
```

## Third-Party Toolset Examples

### Following llm-do Convention

```python
# mycompany/toolsets/database.py
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import BaseApprovalToolset

class DatabaseToolsetInner(AbstractToolset):
    def __init__(self, config: dict, context: Any):
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
        # ... implementation


class DatabaseToolset(BaseApprovalToolset):
    inner_class = DatabaseToolsetInner
```

Usage:
```yaml
toolsets:
  mycompany.toolsets.database.DatabaseToolset:
    connection_string: "${DATABASE_URL}"
    readonly: true
```

### Using Arbitrary pydantic-ai Toolset

```yaml
# Any pydantic-ai toolset works - gets wrapped automatically
toolsets:
  some_library.FileSystemToolset:
    root_path: "/data"
    _approval_config:
      read_file: {pre_approved: true}
      write_file: {pre_approved: false}
```

## Open Questions

1. **Validation**: How to validate config before passing to toolset? JSON schema per toolset?
2. **Aliases**: Support short names like `shell` -> `llm_do.toolsets.shell.ShellToolset`?
3. **Security**: Should there be an allowlist of loadable toolset classes?
4. **Context protocol**: Should we define a Protocol for context instead of using WorkerContext directly?
5. **Inner class detection**: Is inspecting `__init__` signature reliable enough?
