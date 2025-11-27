# Tool Approval Architecture

> **Related document**: See [cli_approval_user_stories.md](cli_approval_user_stories.md) for detailed CLI interaction stories and acceptance criteria. This document focuses on the technical architecture; the user stories document covers the operator experience.

> **Portability**: The core approval types (`ApprovalRequest`, `ApprovalContext`, `ApprovalAware`) are designed to be framework-agnostic. They can be extracted into a standalone package for use with any LLM agent framework, not just llm-do or PydanticAI.

## Problem Statement

The current llm-do approval system has approval configuration split across two places:

1. **Tool-specific config** (e.g., `sandbox.paths`, `shell_rules`) - defines what the tool can do
2. **`tool_rules`** - defines which tools need approval

This creates several problems:

- **Naming mismatch**: Tools expose names like `write_file` but `tool_rules` uses `sandbox.write`
- **Duplicate configuration**: Users configure the same concern in two places
- **Leaky abstraction**: The filesystem sandbox has llm-do's `approval_controller` check baked into its `call_tool()` method
- **Hard to extend**: Adding a new tool requires understanding both systems

Additionally, we want to:
- Keep tools usable as bare PydanticAI tools without approval
- Support an OS-level sandbox (Seatbelt/bwrap) that enforces hard boundaries
- Have a single source of truth for what's allowed

## Design Goals

1. **Tools own their approval semantics** - only the tool understands what an operation means
2. **Approval is optional/additive** - bare PydanticAI tools work without modification
3. **Single configuration point** - no `tool_rules` separate from tool config
4. **Clean layering** - approval, validation, and OS enforcement are separate concerns
5. **Composable** - tools can be wrapped with approval without changing their implementation

## Proposed Architecture

### Three Layers

```
┌─────────────────────────────────────────────────────────┐
│  1. Approval Layer (llm-do runtime)                     │
│     - Asks "should we do this?" before execution        │
│     - Interactive prompts, session memory, policies     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  2. Tool Layer (Python)                                 │
│     - Validates arguments (paths in sandbox, etc.)      │
│     - Executes the operation                            │
│     - Provides approval metadata to layer above         │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  3. OS Sandbox Layer (Seatbelt/bwrap)                   │
│     - Hard enforcement, last line of defense            │
│     - No prompts, just blocks unauthorized access       │
│     - Config derived from tool layer config             │
└─────────────────────────────────────────────────────────┘
```

### Tool Approval Interface

Tools that support approval implement an optional interface:

```python
from typing import Protocol, Optional, Any, Literal, Callable
from pydantic import BaseModel, Field

class ApprovalPresentation(BaseModel):
    """Rich presentation data for approval UI.

    This is optional—tools can return just the basic ApprovalRequest fields
    and let the approval controller generate presentation from the payload.
    """
    type: Literal["text", "diff", "file_content", "command", "structured"]
    content: str
    language: Optional[str] = None  # For syntax highlighting
    metadata: dict[str, Any] = Field(default_factory=dict)  # e.g., {"full_content": "..."} for pager

class ApprovalContext(BaseModel):
    """Context passed to check_approval.

    The core fields (tool_name, args) are framework-agnostic. The metadata
    dict allows framework-specific data (run IDs, session IDs, caller info)
    without polluting the base interface.
    """
    tool_name: str
    args: dict[str, Any]

    # Framework-specific context goes here (run_id, session_id, caller, etc.)
    # This keeps the core interface stable across different agent frameworks.
    metadata: dict[str, Any] = Field(default_factory=dict)

class ApprovalRequest(BaseModel):
    """Returned by a tool to request approval before execution.

    This is the single canonical shape for all approval requests.
    The payload field is the structured fingerprint used for session
    approval matching—tools control what goes here.
    """
    # Stable identifier: what the operator sees and what gets logged
    tool_name: str
    description: str

    # Structured fingerprint for "approve for session" matching.
    # Tools control what goes here (can omit secrets, normalize paths, etc.)
    # See "Session Approval Matching" section for matching semantics.
    payload: dict[str, Any]

    # Optional rich UI hints. If None, the approval controller renders
    # a default display from tool_name + payload.
    presentation: Optional[ApprovalPresentation] = None

    # Optional grouping for batch approvals
    group_id: str | None = None

class ApprovalAware(Protocol):
    """Protocol for tools that can request approval.

    This is intentionally synchronous. Approval checking should be a fast,
    pure computation based on tool config and arguments. Any I/O-heavy work
    (like generating diffs for presentation) should be done lazily by the
    approval controller, not in check_approval().
    """

    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Inspect context and return approval request, or None if no approval needed.

        Returns:
            None - No approval needed, proceed with execution
            ApprovalRequest - Approval required before execution

        Raises:
            PermissionError - Operation is blocked entirely (not just needs approval)
        """
        ...
```

A bare tool function doesn't implement this—it just executes. An approval-aware tool implements `check_approval` to declare when it needs user consent.

#### Why `check_approval` is Synchronous

The interface is deliberately sync because:

1. **Approval checking is a policy decision**, not I/O. The tool examines its config and the arguments to decide if approval is needed—this is pure computation.

2. **Presentation generation can be lazy**. If a diff is needed, the approval controller can generate it *after* checking session cache. No point computing a diff for an already-approved operation.

3. **Simpler integration**. Sync protocols are easier to implement and compose. Async would force every tool wrapper to be async even when unnecessary.

#### Factory Function for Simple Cases

For tools that just need basic approval with tool name and args display:

```python
def simple_approval_request(
    tool_name: str,
    args: dict[str, Any],
    *,
    description: str | None = None,
    exclude_keys: set[str] | None = None,
) -> ApprovalRequest:
    """Create an ApprovalRequest with sensible defaults.

    Args:
        tool_name: Name of the tool requesting approval
        args: Tool arguments
        description: Human-readable description. If None, auto-generated from tool_name and args.
        exclude_keys: Keys to omit from payload (e.g., large content, secrets)

    Returns:
        ApprovalRequest ready to return from check_approval()
    """
    # Build payload, optionally excluding certain keys
    if exclude_keys:
        payload = {k: v for k, v in args.items() if k not in exclude_keys}
    else:
        payload = dict(args)

    # Auto-generate description if not provided
    if description is None:
        args_str = ', '.join(f'{k}={v!r}' for k, v in args.items())
        description = f"{tool_name}({args_str})"

    return ApprovalRequest(
        tool_name=tool_name,
        description=description,
        payload=payload,
    )
```

This allows tools to start simple and add richer presentation later without changing the architecture.

#### Phase 1: Simple Display

The CLI displays tool name and args directly:
```
Tool: write_file
Args: {"path": "notes/log.txt", "content": "Meeting notes..."}

[y] Approve  [n] Reject  [s] Approve for session
```

#### Phase 2: Rich Presentation

When `presentation` is provided, the CLI renders it appropriately:

| Type | Use Case | Rendering |
|------|----------|-----------|
| `text` | Simple messages | Plain text block |
| `diff` | File edits | Unified diff with colors (+green/-red) |
| `file_content` | New file creation | Syntax-highlighted content |
| `command` | Shell execution | Command with working directory |
| `structured` | Complex data | JSON/YAML formatted display |

Example with diff:
```
┌─ write_file ──────────────────────────────────────────────┐
│ Edit notes/report.md                                       │
├────────────────────────────────────────────────────────────┤
│ @@ -1,3 +1,5 @@                                            │
│  # Weekly Report                                           │
│ -## Summary                                                │
│ +## Executive Summary                                      │
│ +Key findings from this week:                              │
├────────────────────────────────────────────────────────────┤
│ [y] Approve  [n] Reject  [s] Approve for session           │
└────────────────────────────────────────────────────────────┘
```

### Separation of Concerns: Tools vs Approval Controller

**Tools are responsible for:**
- Deciding whether an operation needs approval (based on tool config like `write_approval`, `shell_rules`)
- Returning `ApprovalRequest` when approval is needed, or `None` when pre-approved
- Raising `PermissionError` when an operation is blocked entirely
- Generating the `description`, `payload`, and optional `presentation`
- Never knowing about CLI flags (`--strict`, `--approve-all`), TTY state, or session memory

**Approval Controller is responsible for:**
- Interpreting `ApprovalRequest` together with runtime mode
- Session memory ("approve for session") using `payload` for equivalence matching
- Displaying the approval prompt (using `presentation` if available, otherwise rendering from payload)
- Generating lazy presentation (diffs, syntax highlighting) when needed
- Non-interactive mode detection (TTY check)

This separation keeps tools portable—the same `check_approval` logic works in CLI, CI, or AG-UI scenarios.

| `check_approval()` returns | Interactive (default) | `--approve-all` | `--strict` |
|----------------------------|----------------------|-----------------|------------|
| `None` | Execute | Execute | Execute |
| `ApprovalRequest` | Prompt user | Auto-approve | Auto-deny |
| Raises `PermissionError` | Block | Block | Block |

The semantics are simple:
- **`None`**: Tool says "no approval needed"—all modes execute immediately
- **`ApprovalRequest`**: Tool says "ask the user"—behavior depends on mode
- **`PermissionError`**: Tool says "never allowed"—all modes block

### Runtime Flow

```python
import asyncio
from typing import Callable, Any

async def execute_tool(
    tool_func: Callable,
    tool_name: str,
    args: dict,
    approval_controller: ApprovalController,
    context_metadata: dict[str, Any] | None = None,
):
    """Execute a tool with approval checking.

    Args:
        tool_func: The tool function/callable to execute
        tool_name: Name of the tool (for display and logging)
        args: Arguments to pass to the tool
        approval_controller: Handles approval prompts and session memory
        context_metadata: Optional framework-specific context (run_id, session_id, etc.)
    """
    # 1. Check if tool is approval-aware
    if hasattr(tool_func, 'check_approval'):
        ctx = ApprovalContext(
            tool_name=tool_name,
            args=args,
            metadata=context_metadata or {},
        )

        # check_approval is sync—it's just a policy decision
        approval_request = tool_func.check_approval(ctx)

        if approval_request is not None:
            # 2. Ask approval controller (may prompt user, check session cache, etc.)
            # This is async because it may involve I/O (user input, lazy diff generation)
            decision = await approval_controller.request_approval(approval_request)

            if not decision.approved:
                raise PermissionError(f"Approval denied: {decision.note}")

    # 3. Execute the tool
    if asyncio.iscoroutinefunction(tool_func):
        return await tool_func(**args)
    else:
        return tool_func(**args)
```

### Example: Filesystem Sandbox

Configuration becomes self-contained:

```yaml
sandbox:
  paths:
    notes:
      root: ./notes
      mode: rw
      suffixes: [.txt, .log]
      write_approval: true   # Writes to this path need approval
      read_approval: false   # Reads don't need approval
    cache:
      root: ./cache
      mode: rw
      write_approval: false  # Cache writes are pre-approved
```

The sandbox's `check_approval` implementation:

```python
class FileSandbox:
    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        if ctx.tool_name == "write_file":
            path = ctx.args["path"]
            sandbox_name, resolved, config = self._find_path_for(path)

            if not config:
                raise PermissionError(f"Path not in any sandbox: {path}")

            if config.write_approval:
                return ApprovalRequest(
                    tool_name=ctx.tool_name,
                    description=f"Write to {sandbox_name}:{path}",
                    payload={"sandbox": sandbox_name, "path": path},
                    # Note: presentation (diff) is generated lazily by the controller
                )

        elif ctx.tool_name == "read_file":
            path = ctx.args["path"]
            sandbox_name, resolved, config = self._find_path_for(path)

            if not config:
                raise PermissionError(f"Path not in any sandbox: {path}")

            if config.read_approval:
                return ApprovalRequest(
                    tool_name=ctx.tool_name,
                    description=f"Read from {sandbox_name}:{path}",
                    payload={"sandbox": sandbox_name, "path": path},
                )

        return None  # No approval needed
```

### Example: Shell Tool

Shell commands are complex - the tool must interpret the command to determine approval needs:

```yaml
shell:
  default:
    allowed: true
    approval: true  # Unknown commands need approval
  rules:
    - pattern: "git status"
      approval: false  # Safe, read-only
    - pattern: "git add"
      approval: true
      description: "Stage files for commit"
    - pattern: "git commit"
      approval: true
      description: "Create a commit"
    - pattern: "rm"
      allowed: false  # Never allow rm
    - pattern: "pytest"
      approval: false
      sandbox_paths: [output]  # Only if paths are in sandbox
```

The shell tool's `check_approval`:

```python
class ShellTool:
    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        command = ctx.args["command"]
        parsed = parse_command(command)

        # Find matching rule
        for rule in self.config.rules:
            if command_matches(command, rule.pattern):
                if not rule.allowed:
                    raise PermissionError(f"Command blocked: {rule.pattern}")

                # Check sandbox_paths constraint if specified
                if rule.sandbox_paths:
                    if not self._paths_in_sandbox(parsed, rule.sandbox_paths):
                        continue  # Try next rule

                if rule.approval:
                    return ApprovalRequest(
                        tool_name=ctx.tool_name,
                        description=rule.description or f"Execute: {command[:50]}...",
                        payload={"command": command, "rule": rule.pattern},
                    )
                else:
                    return None  # Pre-approved by rule

        # No rule matched, use default
        if self.config.default.approval:
            return ApprovalRequest(
                tool_name=ctx.tool_name,
                description=f"Execute shell command: {command[:50]}...",
                payload={"command": command},
            )

        return None  # Default allows without approval
```

### Example: Custom Tool

Use the `@requires_approval` decorator to add approval to custom tools:

```python
from tool_approval import requires_approval  # Framework-agnostic package

@requires_approval()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    # ... implementation ...
    return f"Email sent to {to}"
```

For more control over description and payload:

```python
@requires_approval(
    description=lambda args: f"Send email to {args['to']}: {args['subject']}",
    exclude_keys={"body"},  # Omit body from payload to avoid logging sensitive content
)
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    # ... implementation ...
    return f"Email sent to {to}"
```

#### Decorator Implementation

```python
import functools
import inspect
from typing import Callable, Optional, Any

def requires_approval(
    *,
    description: str | Callable[[dict[str, Any]], str] | None = None,
    exclude_keys: set[str] | None = None,
    payload: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
):
    """Decorator that adds check_approval() to a tool function.

    Args:
        description: Static string or callable that generates description from args.
                    If None, auto-generates from function name and args.
        exclude_keys: Keys to exclude from auto-generated payload.
        payload: Custom payload generator. If provided, exclude_keys is ignored.

    Example:
        @requires_approval()
        def delete_file(path: str) -> str:
            ...

        @requires_approval(
            description=lambda args: f"Delete {args['path']}",
            exclude_keys={"force"},
        )
        def delete_file(path: str, force: bool = False) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = func.__name__

        def check_approval(ctx: ApprovalContext) -> Optional[ApprovalRequest]:
            # Generate description
            if description is None:
                args_str = ', '.join(f'{k}={v!r}' for k, v in ctx.args.items())
                desc = f"{tool_name}({args_str})"
            elif callable(description):
                desc = description(ctx.args)
            else:
                desc = description

            # Generate payload
            if payload is not None:
                pl = payload(ctx.args)
            elif exclude_keys:
                pl = {k: v for k, v in ctx.args.items() if k not in exclude_keys}
            else:
                pl = dict(ctx.args)

            return ApprovalRequest(
                tool_name=tool_name,
                description=desc,
                payload=pl,
            )

        # Attach check_approval to the function
        func.check_approval = check_approval
        return func

    return decorator
```

The decorator pattern is preferred because:
- It's easy to add approval to existing functions without modifying them
- It integrates well with any agent framework's tool registration
- The `ApprovalAware` protocol can evolve without breaking tool implementations

### OS Sandbox Integration

The OS sandbox is the last line of defense—it enforces hard boundaries at the process level.

#### Key Invariant: Never Weaker

> **The OS sandbox MUST never be less restrictive than the Python/tool config. It can be stricter, but never looser.**

This means:
- If the filesystem sandbox allows `./data` as writable, the OS sandbox allows `./data` (or a subset)
- If the shell config disables network, the OS sandbox blocks network
- An operator can supply an explicit OS profile that's *more* restrictive than implied by tools, but not less

#### Profile Derivation

```python
def derive_os_sandbox_profile(
    sandbox_config: SandboxConfig,
    shell_config: ShellConfig,
    explicit_profile: Optional[OSProfile] = None,
) -> OSProfile:
    """Generate OS sandbox profile from tool configurations.

    If explicit_profile is provided, intersect it with tool-derived permissions
    (never grant more than explicit allows).
    """

    # Start from tool-derived permissions
    derived = OSProfile()

    # From filesystem sandbox: allowed paths
    for name, path_config in sandbox_config.paths.items():
        resolved_root = resolve_path(path_config.root)
        if path_config.mode == "rw":
            derived.allow_write(resolved_root)
        else:
            derived.allow_read(resolved_root)

    # From shell config: network access
    if shell_config.network:
        derived.allow_network()

    # If explicit profile provided, intersect (never grant more)
    if explicit_profile is not None:
        return derived.intersect(explicit_profile)

    return derived
```

#### `require_os_sandbox` Behavior

When `require_os_sandbox: true` is set:

1. **If OS sandbox can be applied** (supported platform, Seatbelt/bwrap available): proceed normally
2. **If OS sandbox cannot be applied**: the runtime either:
   - **Fails fast** and refuses to start (default, recommended for production)
   - **Runs in degraded mode** that refuses all file/shell tools (opt-in for development)

```yaml
sandbox:
  paths:
    data:
      root: ./data
      mode: rw
  require_os_sandbox: true
  # Optional: allow degraded mode instead of failing
  os_sandbox_fallback: refuse_tools  # or "fail_fast" (default)
```

The OS sandbox is invisible to the approval layer—it's a silent safety net that catches bugs or path traversal escapes in the Python layer.

### Framework Integration

The approval types are designed to work with any LLM agent framework. Here's the general pattern:

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Framework (PydanticAI, LangChain, etc.)              │
│  - Tool registration and execution                          │
│  - Context management                                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Approval Wrapper (framework-specific adapter)              │
│  - Intercepts tool calls                                    │
│  - Builds ApprovalContext from framework context            │
│  - Calls check_approval() before tool execution             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Approval Controller (framework-agnostic)                   │
│  - Interprets ApprovalRequest + runtime mode                │
│  - Displays prompt (CLI, IDE, web UI)                       │
│  - Manages session memory                                   │
└─────────────────────────────────────────────────────────────┘
```

Key integration points:

1. **Tools are native framework tools**: Use your framework's normal tool registration
2. **Context mapping**: The adapter maps framework context to `ApprovalContext.metadata`
3. **Approval-aware wrapper**: Check `hasattr(tool, 'check_approval')` before execution
4. **No framework lock-in**: The core types have no framework dependencies

#### Example: PydanticAI Integration

```python
from pydantic_ai import Agent, RunContext
from tool_approval import ApprovalContext, ApprovalRequest, ApprovalController

async def approval_tool_wrapper(
    tool_func: Callable,
    ctx: RunContext,
    tool_name: str,
    args: dict,
    approval_controller: ApprovalController,
):
    """Wrap a PydanticAI tool with approval checking."""
    if hasattr(tool_func, 'check_approval'):
        approval_ctx = ApprovalContext(
            tool_name=tool_name,
            args=args,
            metadata={
                "run_id": getattr(ctx, 'run_id', None),
                "session_id": getattr(ctx.deps, 'session_id', None),
                "caller": getattr(ctx.deps, 'worker_name', None),
            },
        )
        # check_approval is sync
        request = tool_func.check_approval(approval_ctx)

        if request is not None:
            # request_approval is async (user interaction, lazy presentation)
            decision = await approval_controller.request_approval(request)
            if not decision.approved:
                raise PermissionError(f"Approval denied: {decision.note}")

    # Execute the actual tool
    if asyncio.iscoroutinefunction(tool_func):
        return await tool_func(**args)
    return tool_func(**args)
```

#### Example: LangChain Integration

```python
from langchain_core.tools import BaseTool
from tool_approval import ApprovalContext, ApprovalController

class ApprovalToolWrapper:
    """Wraps LangChain tools with approval checking."""

    def __init__(self, tool: BaseTool, controller: ApprovalController):
        self.tool = tool
        self.controller = controller

    async def invoke(self, args: dict, config: dict | None = None) -> Any:
        if hasattr(self.tool, 'check_approval'):
            ctx = ApprovalContext(
                tool_name=self.tool.name,
                args=args,
                metadata={"config": config} if config else {},
            )
            request = self.tool.check_approval(ctx)

            if request is not None:
                decision = await self.controller.request_approval(request)
                if not decision.approved:
                    raise PermissionError(f"Approval denied: {decision.note}")

        return await self.tool.ainvoke(args, config)
```

### Batch Approvals

When tools produce related operations (e.g., "save project" writes 10 files), they can group approvals using `group_id`:

```python
class FileSandbox:
    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        # ...
        return ApprovalRequest(
            tool_name=ctx.tool_name,
            description=f"Write to {sandbox_name}:{path}",
            payload={"sandbox": sandbox_name, "path": path},
            # batch_id passed via metadata by higher-level orchestration
            group_id=ctx.metadata.get("batch_id"),
        )
```

When multiple `ApprovalRequest`s share a `group_id`, the approval controller *may* present them together as a single approve/deny decision. This keeps batching explicit and tool-controlled rather than having the runtime guess based on timing or similarity.

### Session Approval Matching

When the user selects "approve for session", the approval controller stores the `payload` and skips future prompts for equivalent operations. Here's how matching works:

#### Matching Rules

1. **Exact match by default**: Two payloads match if they are deeply equal (`payload_a == payload_b`)

2. **Tools control granularity**: By choosing what goes in `payload`, tools control what counts as "the same operation":
   ```python
   # Fine-grained: each file is separately approved
   payload={"path": "/data/report.txt"}

   # Coarse-grained: all writes to a sandbox are approved together
   payload={"sandbox": "data"}

   # Command pattern: approve all "git status" commands
   payload={"command_pattern": "git status"}
   ```

3. **Exclude volatile data**: Don't include timestamps, request IDs, or content that changes between calls:
   ```python
   # Bad: content changes, so session approval never matches
   payload={"path": path, "content": content}

   # Good: just the path, content can vary
   payload={"path": path}
   ```

#### Implementation

```python
from dataclasses import dataclass
from enum import Enum

class ApprovalScope(Enum):
    ONCE = "once"           # Just this call
    SESSION = "session"     # Until run ends

@dataclass
class ApprovalDecision:
    approved: bool
    scope: ApprovalScope = ApprovalScope.ONCE
    note: str | None = None

class ApprovalController:
    def __init__(self, mode: str = "interactive"):
        self.mode = mode  # "interactive", "approve_all", "strict"
        self.session_approvals: set[tuple[str, frozenset]] = set()

    def _make_key(self, request: ApprovalRequest) -> tuple[str, frozenset]:
        """Create hashable key for session matching."""
        def freeze(obj):
            if isinstance(obj, dict):
                return frozenset((k, freeze(v)) for k, v in sorted(obj.items()))
            elif isinstance(obj, (list, tuple)):
                return tuple(freeze(x) for x in obj)
            return obj

        return (request.tool_name, freeze(request.payload))

    def is_session_approved(self, request: ApprovalRequest) -> bool:
        return self._make_key(request) in self.session_approvals

    def add_session_approval(self, request: ApprovalRequest) -> None:
        self.session_approvals.add(self._make_key(request))

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Main entry point for approval requests.

        This is where lazy presentation generation happens—only if we
        actually need to prompt the user.
        """
        # 1. Handle non-interactive modes first (no I/O needed)
        if self.mode == "approve_all":
            return ApprovalDecision(approved=True)
        if self.mode == "strict":
            return ApprovalDecision(approved=False, note="Strict mode: approval required")

        # 2. Check session cache BEFORE generating presentation
        if self.is_session_approved(request):
            return ApprovalDecision(approved=True, scope=ApprovalScope.SESSION)

        # 3. Only now do we build rich presentation (diffs, syntax highlighting, etc.)
        #    This is the "lazy" part—expensive I/O only happens when we need to prompt.
        display_request = await self._enrich_presentation(request)

        # 4. Prompt the user
        decision = await self._prompt_user(display_request)

        # 5. Update session cache if user chose "approve for session"
        if decision.approved and decision.scope == ApprovalScope.SESSION:
            self.add_session_approval(request)

        return decision

    async def _enrich_presentation(self, request: ApprovalRequest) -> ApprovalRequest:
        """Generate rich presentation if not already provided.

        This is where we do expensive I/O like reading files for diffs,
        syntax highlighting, etc. Only called when we need to prompt.
        """
        if request.presentation is not None:
            return request  # Tool already provided presentation

        # Generate default presentation based on tool type
        # (In practice, this would dispatch to tool-specific presenters)
        return request  # For Phase 1, just use description + payload

    async def _prompt_user(self, request: ApprovalRequest) -> ApprovalDecision:
        """Display prompt and wait for user input.

        Implementation depends on UI (CLI, IDE, web).
        """
        # ... CLI/UI specific code ...
        raise NotImplementedError("Subclass must implement _prompt_user")
```

#### Guidelines for Tool Authors

| Scenario | Payload Strategy |
|----------|-----------------|
| File operations | Include path, exclude content |
| Shell commands | Include command or pattern, exclude output |
| API calls | Include endpoint + method, exclude body/response |
| Database queries | Include query pattern, exclude parameters |

## Key Changes from Current Implementation

1. **No more `tool_rules` for built-in tools** - approval config moves into tool config
2. **Tools return `ApprovalRequest`** - contains description + payload (Phase 1), optionally rich presentation (Phase 2)
3. **Consistent naming** - tool name in `ApprovalRequest` matches what LLM sees (`write_file` not `sandbox.write`)
4. **Runtime is approval-agnostic** - just calls `check_approval()` and displays what it gets back

## Migration Path

1. **Phase 1**: Implement `check_approval` in filesystem sandbox and shell tool; CLI displays description + payload
2. **Phase 2**: Add `ApprovalPresentation` support (diffs, syntax highlighting); tools without presentation fall back to Phase 1
3. **Phase 3**: Deprecate `tool_rules` for built-in tools (emit warnings, document migration)
4. **Phase 4**: Remove `tool_rules`; `@requires_approval` decorator is the standard for custom tools

## Rich Presentation (Phase 2)

Tools can provide rich presentation via `ApprovalRequest.presentation`:

| Type | Use Case | Rendering |
|------|----------|-----------|
| `text` | Simple messages | Plain text |
| `diff` | File edits | Unified diff with colors |
| `file_content` | New files | Syntax-highlighted content |
| `command` | Shell | Command with working directory |
| `structured` | API calls | JSON/YAML formatted |

### Content Conventions

1. **Terminal-safe**: No raw binary in `content`; truncate large content
2. **Full content in metadata**: `metadata["full_content"]` for `[v]iew` pager option
3. **Binary files**: Show type and size only (`"Binary file: image/png (2.3 KB)"`)

```python
# Truncation helper
def truncate_for_display(content: str, max_lines: int = 50) -> str:
    lines = content.split('\n')
    if len(lines) > max_lines:
        return '\n'.join(lines[:max_lines]) + f"\n\n... [{len(lines) - max_lines} more lines]"
    return content
```

### CLI Rendering Example

```
┌─ write_file ──────────────────────────────────────────────┐
│ Edit notes/report.md                                       │
├────────────────────────────────────────────────────────────┤
│ @@ -1,3 +1,5 @@                                            │
│  # Weekly Report                                           │
│ -## Summary                                                │
│ +## Executive Summary                                      │
│ +Key findings from this week:                              │
├────────────────────────────────────────────────────────────┤
│ [y] Approve  [n] Reject  [s] Session  [v] View full        │
└────────────────────────────────────────────────────────────┘
```

## Design Decisions

These were originally open questions, now resolved:

1. **Presentation generation is lazy.** The approval controller generates diffs and syntax highlighting *after* checking session cache. Tools just provide `payload`; rich presentation is the controller's responsibility.

2. **`--strict` respects tool pre-approval.** If a tool returns `None` from `check_approval()`, it means "no approval needed"—this is respected in all modes including strict. Strict mode only auto-denies when tools explicitly return an `ApprovalRequest`.

3. **`check_approval()` is synchronous.** Approval checking is a policy decision based on config and arguments—pure computation, no I/O. Async work (user prompts, diff generation) happens in the controller.

## Open Questions

1. **How does this interact with MCP tools?** MCP tools come from external servers—can they declare approval requirements? Options:
   - MCP server provides approval metadata in tool definition
   - Runtime wraps MCP tools with configurable approval rules
   - MCP tools are always approval-required by default

2. **Should there be a standalone `tool-approval` package?** The core types (`ApprovalRequest`, `ApprovalContext`, `ApprovalAware`, `requires_approval`) have no framework dependencies. Extracting them would make adoption easier for non-llm-do users.

3. **Wildcard/pattern matching for session approvals?** Currently session matching is exact. Should tools be able to specify patterns (e.g., "approve all writes to `./data/*`")? This adds complexity but would reduce prompt fatigue for batch operations.
