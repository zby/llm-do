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
  # llm-do convention toolset (has needs_approval) → wrapped with ApprovalToolset
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

  # Arbitrary pydantic-ai toolset (no needs_approval) → wrapped with SimpleApprovalToolset
  some_library.SomeToolset:
    some_option: value
    _approval_config:
      some_tool: {pre_approved: true}
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

    Three patterns:
    1. Already an approval wrapper → instantiate directly
    2. Has needs_approval() method → wrap with ApprovalToolset
    3. No needs_approval() → wrap with SimpleApprovalToolset
    """
    toolset_class = _import_class(class_path)
    config = dict(config)  # copy to avoid mutation

    # Pattern 1: Already an approval wrapper - instantiate directly
    if issubclass(toolset_class, (ApprovalToolset, SimpleApprovalToolset)):
        return toolset_class(
            config=config,
            context=context,
            approval_callback=approval_callback,
            memory=memory,
        )

    # Instantiate the toolset (llm-do convention: config, context)
    toolset = toolset_class(config=config, context=context)

    # Pattern 2: Has needs_approval - wrap with ApprovalToolset
    if hasattr(toolset, 'needs_approval'):
        return ApprovalToolset(
            inner=toolset,
            approval_callback=approval_callback,
            memory=memory,
        )

    # Pattern 3: No needs_approval - wrap with SimpleApprovalToolset
    approval_config = config.pop("_approval_config", {})
    return SimpleApprovalToolset(
        inner=toolset,
        approval_callback=approval_callback,
        memory=memory,
        config=approval_config,
    )


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

Toolsets following the llm-do convention:

1. **Implement `AbstractToolset`**: Standard pydantic-ai toolset interface
2. **Accept `(config, context)` in `__init__`**: Receives config dict and WorkerContext
3. **Implement `needs_approval()` method** (optional): Enables smart approval logic

The factory uses **duck typing** to detect `needs_approval()`:
- If present → wrap with `ApprovalToolset` (calls `needs_approval()` before each tool)
- If absent → wrap with `SimpleApprovalToolset` (uses `_approval_config` from config)

```python
# llm_do/toolsets/shell.py
from pydantic_ai.toolsets import AbstractToolset

class ShellToolset(AbstractToolset):
    """Shell command execution with approval logic."""

    def __init__(self, config: dict, context: "WorkerContext"):
        self.sandbox = context.sandbox
        self.config = config

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        """Approval logic lives here, close to the implementation.

        Returns:
            False: Pre-approved, no user prompt
            True: Requires approval with default description
            dict: Requires approval with custom {"description": "..."}
        """
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
```

The factory automatically wraps based on duck typing:

```python
# Factory detects needs_approval and wraps appropriately
toolset = ShellToolset(config=config, context=context)
if hasattr(toolset, 'needs_approval'):
    wrapped = ApprovalToolset(inner=toolset, ...)  # uses needs_approval()
else:
    wrapped = SimpleApprovalToolset(inner=toolset, config=approval_config, ...)
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
2. Update toolsets to accept `(config, context)` and implement `needs_approval()`
3. Update `WorkerDefinition.toolsets` to use class paths as keys
4. Replace hardcoded toolset creation in `execution.py` with `build_toolsets()`
5. Add backward compatibility layer for old config format (optional)

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

class DatabaseToolset(AbstractToolset):
    """Database toolset with approval logic."""

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
5. **Duck typing vs Protocol**: Currently using `hasattr(toolset, 'needs_approval')` for detection. Could use a Protocol for better type checking, but duck typing is simpler and sufficient.
