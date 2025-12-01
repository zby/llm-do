# Toolset Plugin Architecture

## Overview

This document proposes a plugin architecture for toolsets in llm-do, enabling:
1. Workers to declare which toolsets they use by class name
2. Dynamic loading of toolsets (including third-party)
3. Simplified ApprovalToolset subclasses with no custom `__init__`
4. Clean dependency injection via WorkerContext

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

### Worker Configuration

Workers declare toolsets by fully-qualified class name:

```yaml
# worker.yaml
toolsets:
  llm_do.shell_toolset.ShellApprovalToolset:
    rules:
      - pattern: "git *"
        approval_required: false
    default:
      allowed: true
      approval_required: true

  llm_do.delegation_toolset.DelegationApprovalToolset:
    allow_workers: ["helper", "analyzer"]

  # Third-party toolset
  mycompany.toolsets.DatabaseToolset:
    connection_string: "postgres://..."
```

### ApprovalToolset Base Class

Add a `create` classmethod to `ApprovalToolset` in `pydantic-ai-blocking-approval`:

```python
class ApprovalToolset(AbstractToolset):
    """Wraps a toolset with synchronous approval checking."""

    # Subclasses set this to their default inner toolset class
    default_inner_class: type[AbstractToolset] = None

    def __init__(
        self,
        inner: AbstractToolset,
        approval_callback: Callable[[ApprovalRequest], ApprovalDecision],
        memory: Optional[ApprovalMemory] = None,
        config: Optional[dict] = None,
    ):
        self._inner = inner
        self._approval_callback = approval_callback
        self._memory = memory or ApprovalMemory()
        self.config = config or {}

    @classmethod
    def create(
        cls,
        config: dict,
        context: Any,
        approval_callback: Callable[[ApprovalRequest], ApprovalDecision],
        memory: Optional[ApprovalMemory] = None,
        inner_class: Optional[type[AbstractToolset]] = None,
    ) -> "ApprovalToolset":
        """Factory method to create toolset from config and context.

        Subclasses set `default_inner_class` to specify which inner toolset to create.
        The inner class can be overridden at runtime via `inner_class` parameter.
        The inner class must accept (config, context) in its __init__.

        Args:
            config: Toolset configuration dict from worker definition
            context: Runtime context (e.g., WorkerContext) with dependencies
            approval_callback: Callback for approval decisions
            memory: Optional approval memory for session caching
            inner_class: Override the default inner class (optional)

        Returns:
            Configured ApprovalToolset instance
        """
        actual_inner_class = inner_class or getattr(cls, "default_inner_class", None)
        if actual_inner_class is None:
            raise NotImplementedError(
                f"{cls.__name__} must set default_inner_class or pass inner_class"
            )
        inner = actual_inner_class(config, context)
        return cls(
            inner=inner,
            approval_callback=approval_callback,
            memory=memory,
            config=config,
        )

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        """Override in subclass for custom approval logic."""
        tool_config = self.config.get(name, {})
        if tool_config.get("pre_approved"):
            return False
        return True

    # ... rest of existing implementation
```

This design allows:
1. Subclasses to set `default_inner_class` for standard behavior
2. Runtime override via `inner_class` parameter
3. Config-driven override (see below)

### Inner Toolset Convention

Inner toolsets accept `(config, context)` and extract dependencies:

```python
class ShellToolsetInner(AbstractToolset[WorkerContext]):
    """Core shell command execution (no approval logic)."""

    def __init__(self, config: dict, context: WorkerContext):
        self.sandbox = context.sandbox
        self.config = config

    async def get_tools(self, ctx) -> dict[str, ToolsetTool]:
        # ... tool definitions

    async def call_tool(self, name, tool_args, ctx, tool) -> Any:
        # ... execution logic
```

```python
class DelegationToolsetInner(AbstractToolset[WorkerContext]):
    """Core worker delegation (no approval logic)."""

    def __init__(self, config: dict, context: WorkerContext):
        self.delegator = context.delegator
        self.creator = context.creator
        self.config = config
```

### Approval Subclasses Become Minimal

With the base class handling creation, subclasses only define:
1. `default_inner_class` - which inner toolset to wrap by default
2. `needs_approval()` - custom approval logic

```python
class ShellApprovalToolset(ApprovalToolset):
    """Shell toolset with pattern-based approval."""

    default_inner_class = ShellToolsetInner

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        if name != "shell":
            return True

        command = tool_args.get("command", "")
        args = parse_command(command)

        allowed, approval_required = match_shell_rules(
            command=command,
            args=args,
            rules=self.config.get("rules", []),
            default=self.config.get("default"),
            file_sandbox=self.sandbox,  # via __getattr__ -> _inner.sandbox
        )

        if not allowed:
            raise PermissionError(f"Command blocked: {command}")
        if not approval_required:
            return False

        return {"description": f"Execute: {command[:80]}"}
```

```python
class DelegationApprovalToolset(ApprovalToolset):
    """Delegation toolset with allow_workers enforcement."""

    default_inner_class = DelegationToolsetInner

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        if name == "worker_call":
            target = tool_args.get("worker", "")
            allow_workers = self.config.get("allow_workers", [])
            if '*' not in allow_workers and target not in allow_workers:
                raise PermissionError(f"Worker '{target}' not allowed")
            return {"description": f"Delegate to: {target}"}

        elif name == "worker_create":
            return {"description": f"Create worker: {tool_args.get('name')}"}

        return True
```

### Generic Execution in execution.py

`execution.py` becomes completely generic:

```python
import importlib

def _import_class(class_path: str) -> type:
    """Dynamically import a class from its fully-qualified path."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

def build_toolsets(
    definition: WorkerDefinition,
    context: WorkerContext,
    approval_callback: Callable,
    memory: ApprovalMemory,
) -> list[AbstractToolset]:
    """Build toolsets from worker definition."""
    toolsets = []

    for class_path, toolset_config in definition.toolsets.items():
        toolset_class = _import_class(class_path)

        # Check for inner_class override in config
        inner_class = None
        if "inner_class" in toolset_config:
            inner_class = _import_class(toolset_config.pop("inner_class"))

        # Uniform creation interface
        toolset = toolset_class.create(
            config=toolset_config,
            context=context,
            approval_callback=approval_callback,
            memory=memory,
            inner_class=inner_class,
        )
        toolsets.append(toolset)

    return toolsets
```

This supports config-driven inner class override:

```yaml
toolsets:
  llm_do.shell_toolset.ShellApprovalToolset:
    inner_class: mycompany.toolsets.MyShellInner  # optional override
    rules: [...]
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

1. **Decoupled execution.py**: No toolset-specific code, just dynamic loading
2. **No boilerplate __init__**: Subclasses only define `default_inner_class` and `needs_approval`
3. **Third-party toolsets**: Just implement the convention, no registration needed
4. **Explicit DI**: Dependencies flow through WorkerContext
5. **Testable**: Easy to mock context for testing toolsets
6. **Flexible inner class**: Can override default inner class via config or parameter

## Migration Path

1. Add `create()` classmethod to `ApprovalToolset` in `pydantic-ai-blocking-approval`
   - See: `/home/zby/llm/pydantic-ai-blocking-approval/TODO.md`
2. Update inner toolsets to accept `(config, context)`
3. Simplify approval subclasses (remove custom `__init__`, set `default_inner_class`)
4. Update `WorkerDefinition.toolsets` to use class paths as keys
5. Replace hardcoded toolset creation in `execution.py` with generic loop
6. Add backward compatibility layer for old config format (optional)

## Default Toolsets

Workers could specify defaults via a special key or inherit from a base:

```yaml
# Option A: Explicit defaults
toolsets:
  _defaults: [shell, delegation]  # Short aliases for built-ins
  llm_do.shell_toolset.ShellApprovalToolset:
    rules: [...]

# Option B: Inherit from profile
extends: default_profile  # Includes standard toolsets
toolsets:
  # Additional or override toolsets
```

## Third-Party Toolset Example

```python
# mycompany/toolsets/database.py
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import ApprovalToolset

class DatabaseToolsetInner(AbstractToolset):
    def __init__(self, config: dict, context: Any):
        self.connection_string = config["connection_string"]
        self.readonly = config.get("readonly", True)

    async def get_tools(self, ctx):
        return {
            "query": ToolsetTool(...),
            "execute": ToolsetTool(...),
        }

    async def call_tool(self, name, tool_args, ctx, tool):
        if name == "query":
            return self._run_query(tool_args["sql"])
        elif name == "execute":
            if self.readonly:
                raise PermissionError("Database is readonly")
            return self._run_execute(tool_args["sql"])

class DatabaseApprovalToolset(ApprovalToolset):
    default_inner_class = DatabaseToolsetInner

    def needs_approval(self, name: str, tool_args: dict) -> bool | dict:
        sql = tool_args.get("sql", "")
        if name == "query" and sql.lower().startswith("select"):
            return False  # Safe reads pre-approved
        return {"description": f"SQL: {sql[:60]}..."}
```

Usage in worker:
```yaml
toolsets:
  mycompany.toolsets.database.DatabaseApprovalToolset:
    connection_string: "${DATABASE_URL}"
    readonly: true
```

## Open Questions

1. **Validation**: How to validate config before passing to toolset? JSON schema per toolset?
2. **Aliases**: Support short names like `shell` -> `llm_do.shell_toolset.ShellApprovalToolset`?
3. **Security**: Should there be an allowlist of loadable toolset classes?
4. **Context protocol**: Should we define a Protocol for context instead of using WorkerContext directly?
