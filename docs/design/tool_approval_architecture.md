# Tool Approval Architecture

> **Related document**: See [cli_approval_user_stories.md](cli_approval_user_stories.md) for detailed CLI interaction stories and acceptance criteria. This document focuses on the technical architecture; the user stories document covers the operator experience.

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
from typing import Protocol, Optional, Any, Literal
from pydantic import BaseModel

class ApprovalPresentation(BaseModel):
    """Rich presentation data for approval UI."""
    type: Literal["text", "diff", "file_content", "command", "structured"]
    content: str
    language: Optional[str] = None  # For syntax highlighting
    metadata: dict[str, Any] = {}

class ApprovalContext(BaseModel):
    """Context passed to check_approval for richer scenarios."""
    tool_name: str
    args: dict[str, Any]

    # Optional fields for richer scenarios
    run_id: str | None = None
    session_id: str | None = None
    caller: str | None = None          # Which worker/agent
    tags: set[str] = set()             # e.g., {"filesystem", "write"}

class ApprovalRequest(BaseModel):
    """Returned by a tool to request approval before execution.

    This is the single canonical shape for all approval requests.
    The payload field is the structured fingerprint used for session
    approval matching—tools can deliberately include/omit/redact fields.
    """
    # Whether this operation MUST be explicitly decided (vs. nice-to-have)
    required: bool = True

    # Stable identifier: what the operator sees and what gets logged
    tool_name: str
    description: str

    # Structured fingerprint for "approve for session" matching
    # Tools control what goes here (can omit secrets, large content, etc.)
    payload: dict[str, Any]

    # Optional rich UI hints
    presentation: Optional[ApprovalPresentation] = None

    # Optional grouping for batch approvals
    group_id: str | None = None

class ApprovalAware(Protocol):
    """Protocol for tools that can request approval."""

    async def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Inspect context and return approval request, or None if no approval needed.

        This is async because some approval checks require I/O (reading existing
        files for diff generation, checking file sizes, probing environment).
        """
        ...
```

A bare PydanticAI tool doesn't implement this - it just executes. An llm-do enhanced tool can implement `check_approval` to declare its needs.

#### Base Implementation for Simple Cases

For tools that just need basic approval with tool name and args display:

```python
class SimpleApprovalRequest(ApprovalRequest):
    """Convenience class that derives description and payload from tool_name and args."""

    @classmethod
    def from_args(cls, tool_name: str, args: dict[str, Any], required: bool = True) -> "SimpleApprovalRequest":
        return cls(
            required=required,
            tool_name=tool_name,
            description=f"{tool_name}({', '.join(f'{k}={v!r}' for k, v in args.items())})",
            payload={"tool_name": tool_name, **args},
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
- Returning an `ApprovalRequest` with `required=True/False`
- Generating the `description`, `payload`, and optional `presentation`
- Never knowing about CLI flags (`--strict`, `--approve-all`), TTY state, or session memory

**Approval Controller is responsible for:**
- Interpreting `required` together with runtime mode:
  - Interactive default: prompt for any `ApprovalRequest`
  - `--approve-all`: auto-approve even when `required=True`
  - `--strict`: auto-deny any `ApprovalRequest`, regardless of `required`
- Session memory ("approve for session") using `payload` for equivalence matching
- Displaying the approval prompt (using `presentation` if available)
- Non-interactive mode detection (TTY check)

This separation keeps tools portable—the same `check_approval` logic works in CLI, CI, or AG-UI scenarios.

| Mode | `required=True` | `required=False` |
|------|-----------------|------------------|
| Interactive (default) | Prompt user | Prompt user |
| `--approve-all` | Auto-approve | Auto-approve |
| `--strict` | Auto-deny | Auto-approve (tool says it's pre-approved) |

### Runtime Flow

```python
async def execute_tool(tool, tool_name: str, args: dict, approval_controller, run_context):
    # 1. Check if tool is approval-aware
    if hasattr(tool, 'check_approval'):
        ctx = ApprovalContext(
            tool_name=tool_name,
            args=args,
            run_id=run_context.run_id,
            session_id=run_context.session_id,
            caller=run_context.caller,
        )
        approval_request = await tool.check_approval(ctx)

        if approval_request is not None:
            # 2. Ask approval controller (interprets request + runtime mode)
            decision = await approval_controller.request_approval(approval_request)

            if not decision.approved:
                raise PermissionError(f"Approval denied: {decision.note}")

    # 3. Execute the tool
    return await tool.call(args)
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
    async def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        if ctx.tool_name == "write_file":
            path = ctx.args["path"]
            sandbox_name, resolved, config = self._find_path_for(path)

            if config.write_approval:
                return ApprovalRequest(
                    required=True,
                    tool_name=ctx.tool_name,
                    description=f"Write to {sandbox_name}:{path}",
                    payload={"sandbox": sandbox_name, "path": path},
                    # presentation added in Phase 2 (diff for existing files, etc.)
                )

        elif ctx.tool_name == "read_file":
            path = ctx.args["path"]
            sandbox_name, resolved, config = self._find_path_for(path)

            if config.read_approval:
                return ApprovalRequest(
                    required=True,
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
    async def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
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
                        required=True,
                        tool_name=ctx.tool_name,
                        description=rule.description or f"Execute: {command[:50]}...",
                        payload={"command": command, "rule": rule.pattern},
                    )
                else:
                    return None  # Pre-approved

        # No rule matched, use default
        if self.config.default.approval:
            return ApprovalRequest(
                required=True,
                tool_name=ctx.tool_name,
                description=f"Execute shell command: {command[:50]}...",
                payload={"command": command},
            )

        return None
```

### Example: Custom Tool

Use the `@requires_approval` decorator to add approval to custom tools:

```python
from llm_do.approval import requires_approval

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
    payload=lambda args: {"to": args["to"], "subject": args["subject"]},
    # Omit body from payload to avoid logging sensitive content
)
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    # ... implementation ...
    return f"Email sent to {to}"
```

The decorator pattern is preferred because:
- It's easier to type-check and document
- It integrates well with PydanticAI's `@agent.tool` / toolset machinery
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

### PydanticAI Integration

This architecture sits on top of PydanticAI's agent and tools model. Here's how the pieces connect:

```
┌─────────────────────────────────────────────────────────────┐
│  PydanticAI Agent                                           │
│  - @agent.tool or Toolset functions                         │
│  - RunContext with dependencies                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  llm-do Runtime Adapter                                     │
│  - Wraps tool execution                                     │
│  - Maps RunContext + ToolDefinition + args → ApprovalContext│
│  - Calls check_approval() before tool execution             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Approval Controller                                        │
│  - Interprets ApprovalRequest + runtime mode                │
│  - Displays prompt (CLI, IDE, AG-UI)                        │
│  - Manages session memory                                   │
└─────────────────────────────────────────────────────────────┘
```

Key integration points:

1. **Tools are PydanticAI tools**: Exposed via `@agent.tool` or as `Toolset` functions
2. **RunContext mapping**: The runtime extracts `run_id`, `session_id`, etc. from PydanticAI's `RunContext` to build `ApprovalContext`
3. **Approval-aware wrapper**: The runtime wraps tool execution to call `check_approval()` when the tool implements `ApprovalAware`
4. **No second abstraction**: We don't re-invent tool registration; we just add an optional approval check around PydanticAI's existing machinery

```python
# Example: Integrating with PydanticAI agent
from pydantic_ai import Agent, RunContext
from llm_do.approval import ApprovalContext, ApprovalRequest

async def approval_tool_wrapper(
    tool_func,
    ctx: RunContext,
    tool_name: str,
    args: dict,
    approval_controller,
):
    """Wrap a PydanticAI tool with approval checking."""
    if hasattr(tool_func, 'check_approval'):
        approval_ctx = ApprovalContext(
            tool_name=tool_name,
            args=args,
            run_id=ctx.run_id if hasattr(ctx, 'run_id') else None,
            session_id=getattr(ctx.deps, 'session_id', None),
            caller=getattr(ctx.deps, 'worker_name', None),
        )
        request = await tool_func.check_approval(approval_ctx)

        if request is not None:
            decision = await approval_controller.request_approval(request)
            if not decision.approved:
                raise PermissionError(f"Approval denied: {decision.note}")

    return await tool_func(**args)
```

### Batch Approvals

When tools produce related operations (e.g., "save project" writes 10 files), they can group approvals using `group_id`:

```python
class FileSandbox:
    async def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        # ...
        return ApprovalRequest(
            required=True,
            tool_name=ctx.tool_name,
            description=f"Write to {sandbox_name}:{path}",
            payload={"sandbox": sandbox_name, "path": path},
            group_id=ctx.tags.get("batch_id"),  # Set by higher-level operation
        )
```

When multiple `ApprovalRequest`s share a `group_id`, the approval controller *may* present them together as a single approve/deny decision. This keeps batching explicit and tool-controlled rather than having the runtime guess based on timing or similarity.

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

## Open Questions

1. **How does this interact with MCP tools?** MCP tools come from external servers—can they declare approval requirements? Options:
   - MCP server provides approval metadata in tool definition
   - llm-do wraps MCP tools with configurable approval rules
   - MCP tools are always approval-required by default

2. **Should presentation generation be lazy?** Generating diffs for large files is expensive—only do it if approval is actually required and not session-cached? Proposed: Yes, the runtime should check session cache *before* calling `check_approval()`.

3. **How does `--strict` mode interact with tool-level config?** If a path has `write_approval: false`, does `--strict` still block it? Proposed: No, tool-level pre-approval (`required=False` or returning `None`) is respected even in strict mode—strict mode only auto-denies `required=True` requests.
