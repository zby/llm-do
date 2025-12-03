# SOLID Principles Code Review: llm-do

**Date**: 2025-12-03

## Executive Summary

The codebase demonstrates **strong SOLID adherence overall**, with a well-designed protocol-based architecture that eliminates circular dependencies and enables extensibility. There are a few areas for improvement.

---

## S - Single Responsibility Principle

### Strengths

1. **Clean module separation**: Each module has focused responsibility
   - `runtime.py` → orchestration
   - `execution.py` → agent running
   - `registry.py` → persistence
   - `toolset_loader.py` → factory logic
   - Each toolset → one capability domain

2. **Helper extraction**: `_prepare_worker_context()` and `_handle_result()` properly extract shared logic

### Issues

**1. `WorkerContext` is a "God Object"** (`types.py:223-248`)

```python
@dataclass
class WorkerContext:
    registry: Any
    worker: WorkerDefinition
    attachment_validator: Optional[AttachmentValidator]
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: Any
    sandbox: Optional[AbstractToolset] = None
    attachments: List[AttachmentPayload] = field(default_factory=list)
    message_callback: Optional[MessageCallback] = None
    custom_tools_path: Optional[Path] = None
```

This carries 10 different concerns. Consider splitting into:
- `RuntimeDeps` (registry, approval_controller)
- `WorkerConfig` (worker, effective_model, creation_defaults)
- `IOContext` (sandbox, attachments, attachment_validator)
- `CallbackContext` (message_callback)

**2. `DelegationToolset._prepare_attachments` mixes concerns** (`delegation_toolset.py:205-240`)

This method does three things:
- Validates attachments
- Checks approvals
- Constructs payloads

Consider extracting approval checking to a separate method.

---

## O - Open/Closed Principle

### Strengths

1. **Excellent plugin architecture** (`toolset_loader.py:27-32`)
```python
ALIASES: Dict[str, str] = {
    "shell": "llm_do.shell.toolset.ShellToolset",
    "delegation": "llm_do.delegation_toolset.DelegationToolset",
    "filesystem": "pydantic_ai_filesystem_sandbox.FileSystemToolset",
    "custom": "llm_do.custom_toolset.CustomToolset",
}
```
New toolsets can be added without modifying existing code - just add class path.

2. **Protocol-based extension** (`protocols.py`): Any sandbox implementation works if it satisfies the protocol.

3. **AgentRunner type alias** (`types.py:267-273`): Allows swapping execution strategies.

### Issues

**1. ~~`build_server_side_tools` uses if/elif chain~~ (FIXED)**

Implemented `SERVER_SIDE_TOOL_FACTORIES` registry pattern in `execution.py:75-87`. Also updated deprecated `UrlContextTool` to `WebFetchTool` with backward compatibility.

**2. Special case for FileSystemToolset** (`toolset_loader.py:92-97`)
```python
if class_path == "filesystem" or resolved_path == ALIASES.get("filesystem"):
    toolset = toolset_class(sandbox=context.sandbox)
else:
    toolset = toolset_class(config=config)
```

This breaks OCP - adding new toolsets with different constructor signatures requires modifying this function.

**Recommendation**: Use a toolset factory protocol or introspection-based instantiation.

---

## L - Liskov Substitution Principle

### Strengths

1. **All toolsets properly implement `AbstractToolset`**:
   - `ShellToolset`, `DelegationToolset`, `CustomToolset` all have:
     - `async get_tools(ctx) -> dict[str, ToolsetTool]`
     - `async call_tool(name, tool_args, ctx, tool)`
     - `needs_approval(name, tool_args, ctx)`

2. **`ApprovalToolset` wraps any toolset uniformly** - truly substitutable.

### Issues

**1. ~~`needs_approval` return type inconsistency~~ (FIXED)**

Implemented `ApprovalResult` structured type in `pydantic-ai-blocking-approval`. All toolsets now return:
```python
@dataclass(frozen=True)
class ApprovalResult:
    status: Literal["blocked", "pre_approved", "needs_approval"]
    block_reason: Optional[str] = None

    @classmethod
    def blocked(cls, reason: str) -> ApprovalResult: ...
    @classmethod
    def pre_approved(cls) -> ApprovalResult: ...
    @classmethod
    def needs_approval(cls) -> ApprovalResult: ...
```

Description generation split into separate `get_approval_description()` method (Single Responsibility).

Updated toolsets:
- `ShellToolset` - returns `ApprovalResult`, implements `get_approval_description()`
- `DelegationToolset` - returns `ApprovalResult`, implements `get_approval_description()`
- `FileSystemToolset` - returns `ApprovalResult`, implements `get_approval_description()`

---

## I - Interface Segregation Principle

### Strengths

1. **`FileSandbox` protocol is focused** (`protocols.py:22-106`):
   - Only methods that tools actually need
   - Clear separation of concerns (read/write/list/resolve)

2. **Toolset interface is minimal**:
   - `get_tools()`, `call_tool()` - that's it for basic operation
   - `needs_approval()` only required if toolset handles its own approval logic

### Issues

**1. `WorkerContext` exposes too much to tools** (`types.py:223-248`)

Tools receive the full context but only need subsets:
- Shell tools: only need sandbox for path validation
- Delegation tools: need registry, approval_controller, creation_defaults
- Custom tools: may need nothing

**Recommendation**: Pass narrower interfaces to specific toolsets via their constructor or create focused protocol types.

---

## D - Dependency Inversion Principle

### Strengths

1. **Core design pattern is excellent**:
   - Tools depend on `FileSandbox` protocol, not `Sandbox` concrete class
   - `WorkerContext` carries interfaces, not implementations
   - No circular imports achieved through careful layering

2. **Type annotations use `Any` strategically** to avoid circular imports:
```python
registry: Any  # WorkerRegistry - avoid circular import
approval_controller: Any  # ApprovalController
```

3. **Toolsets receive runtime deps via `ctx.deps`**, not constructor.

### Issues

**1. Direct exception types** (`delegation_toolset.py:90`, `shell/toolset.py:125`)
```python
raise PermissionError(f"Worker '{target_worker}' not in allow_workers list.")
```

Using Python's built-in `PermissionError` couples to a specific exception hierarchy. Consider custom exceptions:
```python
class ToolBlockedError(Exception):
    """Raised when a tool call is blocked by policy."""
    pass

class DelegationNotAllowedError(ToolBlockedError):
    pass
```

**2. Direct import of `pydantic_ai_blocking_approval` in multiple places**

Both `runtime.py` and `delegation_toolset.py` import from this package directly. If you wanted to swap approval systems, you'd need to change multiple files.

**Recommendation**: Create an abstract `ApprovalProvider` protocol in `protocols.py`.

---

## Summary Table

| Principle | Grade | Notes |
|-----------|-------|-------|
| **S** - Single Responsibility | B+ | Good module separation; `WorkerContext` is overloaded |
| **O** - Open/Closed | A- | Excellent plugin system; minor if/elif chains |
| **L** - Liskov Substitution | A+ | All toolsets substitutable; `ApprovalResult` approach standardized |
| **I** - Interface Segregation | B+ | Protocols are focused; context is too broad |
| **D** - Dependency Inversion | A- | Strong protocol use; some concrete exception coupling |

---

## Top 3 Recommended Improvements

1. **Split `WorkerContext`** into focused sub-contexts for different tool needs

2. ~~**Standardize `needs_approval` return type**~~ (DONE) - Implemented `ApprovalResult` in `pydantic-ai-blocking-approval`, split description into `get_approval_description()` method

3. ~~**Registry pattern for server-side tools**~~ (DONE) - Implemented `SERVER_SIDE_TOOL_FACTORIES` in `execution.py`

---

Overall, this is **well-architected code** that clearly demonstrates knowledge of SOLID principles. The protocol-based DI pattern is particularly well-executed and the toolset plugin system is a textbook example of Open/Closed principle.
