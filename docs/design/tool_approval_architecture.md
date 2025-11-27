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
    """Rich presentation data for approval UI (Phase 2)."""
    type: Literal["text", "diff", "file_content", "command", "structured"]
    content: str
    language: Optional[str] = None  # For syntax highlighting
    metadata: dict[str, Any] = {}

class ApprovalRequest(BaseModel):
    """Returned by a tool to request approval before execution."""
    tool_name: str
    args: dict[str, Any]
    # Phase 2: Optional rich presentation
    presentation: Optional[ApprovalPresentation] = None

class ApprovalAware(Protocol):
    """Protocol for tools that can request approval."""

    def check_approval(self, tool_name: str, args: dict[str, Any]) -> Optional[ApprovalRequest]:
        """Inspect args and return approval request, or None if no approval needed."""
        ...
```

A bare PydanticAI tool doesn't implement this - it just executes. An llm-do enhanced tool can implement `check_approval` to declare its needs.

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

### Runtime Flow

```python
async def execute_tool(tool, tool_name: str, args: dict, approval_controller):
    # 1. Check if tool is approval-aware
    if hasattr(tool, 'check_approval'):
        approval_request = tool.check_approval(tool_name, args)

        if approval_request is not None:
            # 2. Ask approval controller (displays tool_name + args to user)
            decision = approval_controller.request_approval(approval_request)

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
    def check_approval(self, tool_name: str, args: dict) -> Optional[ApprovalRequest]:
        if tool_name == "write_file":
            path = args["path"]
            sandbox_name, resolved, config = self._find_path_for(path)

            if config.write_approval:
                return ApprovalRequest(tool_name=tool_name, args=args)

        elif tool_name == "read_file":
            path = args["path"]
            sandbox_name, resolved, config = self._find_path_for(path)

            if config.read_approval:
                return ApprovalRequest(tool_name=tool_name, args=args)

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
    def check_approval(self, tool_name: str, args: dict) -> Optional[ApprovalRequest]:
        command = args["command"]
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
                    return ApprovalRequest(tool_name=tool_name, args=args)
                else:
                    return None  # Pre-approved

        # No rule matched, use default
        if self.config.default.approval:
            return ApprovalRequest(tool_name=tool_name, args=args)

        return None
```

### Example: Custom Tool

A user-defined tool can easily add approval:

```python
from llm_do.approval import ApprovalRequest

def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    # ... implementation ...
    return f"Email sent to {to}"

# Add approval awareness
def send_email_check_approval(tool_name: str, args: dict) -> ApprovalRequest:
    return ApprovalRequest(tool_name=tool_name, args=args)

send_email.check_approval = send_email_check_approval
```

Or using a decorator:

```python
from llm_do.approval import requires_approval

@requires_approval()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    # ... implementation ...
    return f"Email sent to {to}"
```

### OS Sandbox Integration

The OS sandbox config is derived from tool configs, not separately specified:

```python
def derive_os_sandbox_profile(sandbox_config: SandboxConfig, shell_config: ShellConfig) -> OSProfile:
    """Generate OS sandbox profile from tool configurations."""

    profile = OSProfile()

    # From filesystem sandbox: allowed paths
    for name, path_config in sandbox_config.paths.items():
        resolved_root = resolve_path(path_config.root)
        if path_config.mode == "rw":
            profile.allow_write(resolved_root)
        else:
            profile.allow_read(resolved_root)

    # From shell config: network access
    if shell_config.network:
        profile.allow_network()

    return profile
```

The OS sandbox is invisible to the approval layer - it's a safety net that catches bugs or escapes in the Python layer.

## User Stories

> **Note**: For CLI interaction details (pause/resume, keyboard shortcuts, session commands), see [cli_approval_user_stories.md](cli_approval_user_stories.md). The stories below focus on configuration and tool behavior.

### Story 1: Basic Sandbox Write Approval

**As a** user running a note-taking worker
**I want** writes to require my approval
**So that** I can verify what the LLM is saving before it happens

**Configuration:**
```yaml
sandbox:
  paths:
    notes:
      root: ./notes
      mode: rw
      write_approval: true
```

**Flow:**
1. LLM calls `write_file("notes/log.txt", "Meeting notes...")`
2. Sandbox's `check_approval` returns `ApprovalRequest(tool_name="write_file", args={...})`
3. Runtime displays tool name and args, prompts user
4. User approves, file is written

### Story 2: Pre-approved Cache Writes

**As a** developer running a code analysis worker
**I want** cache writes to happen without prompts
**So that** the workflow isn't interrupted for routine operations

**Configuration:**
```yaml
sandbox:
  paths:
    cache:
      root: ./cache
      mode: rw
      write_approval: false
    output:
      root: ./reports
      mode: rw
      write_approval: true
```

**Flow:**
1. LLM calls `write_file("cache/analysis.json", data)` - no prompt, executes
2. LLM calls `write_file("output/report.md", report)` - prompts for approval

### Story 3: Shell Command with Pattern Rules

**As a** user running a git-based worker
**I want** safe git commands to run without approval
**But** destructive commands should require confirmation

**Configuration:**
```yaml
shell:
  rules:
    - pattern: "git status"
      approval: false
    - pattern: "git diff"
      approval: false
    - pattern: "git log"
      approval: false
    - pattern: "git add"
      approval: true
    - pattern: "git commit"
      approval: true
    - pattern: "git push"
      approval: true
    - pattern: "git reset --hard"
      allowed: false
  default:
    approval: true
```

**Flow:**
1. LLM calls `shell("git status")` - executes immediately
2. LLM calls `shell("git add .")` - prompts: "Stage files for commit? [y/n]"
3. LLM calls `shell("git reset --hard")` - blocked, raises PermissionError

### Story 4: Custom Tool with Approval

**As a** developer adding a Slack notification tool
**I want** to require approval before sending messages
**So that** users can review notifications before they're sent

**Implementation:**
```python
@requires_approval(
    description=lambda args: f"Send to #{args['channel']}: {args['message'][:50]}...",
    payload=lambda args: {"channel": args["channel"]}
)
def slack_notify(channel: str, message: str) -> str:
    """Send a Slack notification."""
    client.chat_postMessage(channel=channel, text=message)
    return f"Sent to #{channel}"
```

**Flow:**
1. LLM calls `slack_notify("#general", "Build completed!")`
2. Runtime prompts: "Send to #general: Build completed!? [y/n]"
3. User approves, message is sent

### Story 5: Bare PydanticAI Tool (No Approval)

**As a** developer prototyping quickly
**I want** to use plain PydanticAI tools without approval overhead
**So that** I can iterate fast during development

**Implementation:**
```python
def calculate(expression: str) -> float:
    """Evaluate a math expression."""
    return eval(expression)  # Don't do this in production!
```

**Flow:**
1. Tool has no `check_approval` method
2. Runtime executes directly without any approval check
3. Later, developer can add `@requires_approval` decorator when ready

### Story 6: Session Approval Memory

**As a** user approving repeated similar operations
**I want** to approve once for the session
**So that** I'm not prompted for every identical operation

**Flow:**
1. LLM calls `write_file("notes/log.txt", "Entry 1")`
2. User approves with "approve for session"
3. LLM calls `write_file("notes/log.txt", "Entry 2")` - auto-approved (same path pattern)
4. LLM calls `write_file("notes/other.txt", "Entry 3")` - prompts again (different path)

**Note:** Session memory is in the approval controller, not the tool. The tool just provides the payload; the controller tracks what's been approved.

### Story 7: OS Sandbox as Safety Net

**As a** security-conscious operator
**I want** OS-level enforcement even if Python validation has bugs
**So that** a path traversal bug can't escape the sandbox

**Configuration:**
```yaml
sandbox:
  paths:
    data:
      root: ./data
      mode: rw
  require_os_sandbox: true
```

**Flow:**
1. Filesystem sandbox config specifies `./data` as writable
2. Runtime generates OS profile: only `./data` is writable at process level
3. If a bug allows `write_file("../../etc/passwd", ...)` to reach the OS:
   - Seatbelt/bwrap blocks it
   - Error logged for debugging
4. User never sees this - it's a silent safety net

### Story 8: Approval for Attachment Sharing

**As a** user delegating work between workers
**I want** to approve which files are shared
**So that** sensitive files aren't accidentally passed to other workers

**Configuration:**
```yaml
sandbox:
  paths:
    input:
      root: ./documents
      mode: ro
      read_approval: true  # Approval needed to share files from here
```

**Flow:**
1. Parent worker calls `worker_call("analyzer", attachments=["input/sensitive.pdf"])`
2. Runtime's attachment handling calls sandbox's `check_approval` for the read
3. User prompted: "Share input/sensitive.pdf (2.3MB) with 'analyzer' worker? [y/n]"
4. User approves, file is passed to child worker

## Mapping to CLI User Stories

This architecture supports all scenarios from [cli_approval_user_stories.md](cli_approval_user_stories.md):

| User Story | Architecture Support |
|------------|---------------------|
| **Story 1-3**: Pause, approve, reject | Runtime calls `check_approval()`, displays tool name + args, waits for decision |
| **Story 4**: Pre-approve known-safe tools | Tool config (e.g., `write_approval: false` per path) instead of `tool_rules` |
| **Story 5**: Session approval | `ApprovalController` tracks approved `(tool_name, args)` pairs |
| **Story 6**: `--approve-all` flag | Runtime skips `check_approval()` entirely or auto-approves all requests |
| **Story 7**: `--strict` mode | Runtime rejects any non-None `ApprovalRequest` |
| **Story 8-10**: Shell command approval | Shell tool's `check_approval()` evaluates `shell_rules` |
| **Story 11**: Worker creation approval | `worker.create` tool implements `check_approval()` |
| **Story 12**: Worker delegation approval | `worker.call` tool implements `check_approval()` |
| **Story 13**: File sharing approval | Sandbox's `check_approval()` for reads |
| **Story 14**: Session history | `ApprovalController` exposes list of session-approved `(tool_name, args)` pairs |
| **Story 15**: Non-interactive mode | Runtime checks TTY; requires explicit `--approve-all` or `--strict` |

### Key Changes from Current Implementation

1. **No more `tool_rules` for built-in tools** - approval config moves into tool config
2. **Tools return `ApprovalRequest`** - contains tool name + args (Phase 1), optionally rich presentation (Phase 2)
3. **Consistent naming** - tool name in `ApprovalRequest` matches what LLM sees (`write_file` not `sandbox.write`)
4. **Runtime is approval-agnostic** - just calls `check_approval()` and displays what it gets back

## Migration Path

### Phase 1: Basic approval with tool name + args
- Filesystem sandbox implements `check_approval` based on new per-path config (`write_approval`, `read_approval`)
- Shell tool implements `check_approval` using existing `shell_rules` (already tool-owned)
- Runtime checks for `check_approval` before tool execution
- CLI displays simple format: tool name + args JSON
- `ApprovalRequest.presentation` is always `None`

### Phase 2: Rich presentation
- Add `ApprovalPresentation` support to tools
- Filesystem sandbox generates diffs for file edits, content preview for new files
- Shell tool shows command with working directory context
- CLI renders based on presentation type (diff, file_content, command, etc.)
- Tools without presentation fall back to Phase 1 display

### Phase 3: Deprecate `tool_rules` for built-in tools
- Emit warning when `tool_rules` contains `sandbox.write`, `sandbox.read`, or `shell`
- Document migration: `tool_rules.sandbox.write.approval_required: true` → `sandbox.paths.X.write_approval: true`
- Keep `tool_rules` working during transition

### Phase 4: Remove `tool_rules` for built-in tools
- `tool_rules` only applies to custom tools that don't implement `check_approval`
- Provide `@requires_approval` decorator as the standard way for custom tools

## Phase 2: Rich Presentation Details

> This section details the rich presentation feature planned for Phase 2. In Phase 1, approval prompts show only tool name and args.

A simple "approve Y/N?" prompt is insufficient for many operations. Users need to see **what will actually happen** before approving. Tools provide rich presentation data via the optional `ApprovalRequest.presentation` field.

### Presentation Types

| Type | Use Case | Rendering |
|------|----------|-----------|
| `text` | Simple messages, summaries | Plain text block |
| `diff` | File edits, patches | Unified diff with colors (+green/-red) |
| `file_content` | New file creation | Syntax-highlighted content |
| `command` | Shell execution | Command with syntax highlighting |
| `structured` | Complex data | JSON/YAML formatted display |

### Example: File Edit with Diff

When editing an existing file, show what will change:

```python
class FileSandbox:
    def check_approval(self, tool_name: str, args: dict) -> Optional[ApprovalRequest]:
        if tool_name == "write_file":
            path = args["path"]
            new_content = args["content"]
            sandbox_name, resolved, config = self._find_path_for(path)

            if not config.write_approval:
                return None

            # Generate diff if file exists (Phase 2)
            presentation = None
            if resolved.exists():
                old_content = resolved.read_text()
                diff = generate_unified_diff(
                    old_content, new_content,
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}"
                )
                presentation = ApprovalPresentation(
                    type="diff",
                    content=diff,
                    metadata={"old_size": len(old_content), "new_size": len(new_content)}
                )
            else:
                # New file - show content
                presentation = ApprovalPresentation(
                    type="file_content",
                    content=new_content,
                    language=suffix_to_language(resolved.suffix),
                    metadata={"size": len(new_content)}
                )

            return ApprovalRequest(
                tool_name=tool_name,
                args=args,
                presentation=presentation,
            )
```

### Example: Shell Command Presentation

```python
class ShellTool:
    def check_approval(self, tool_name: str, args: dict) -> Optional[ApprovalRequest]:
        command = args["command"]
        # ... rule matching logic ...

        return ApprovalRequest(
            tool_name=tool_name,
            args=args,
            presentation=ApprovalPresentation(
                type="command",
                content=command,
                language="bash",
                metadata={"cwd": str(self.working_dir)}
            ),
        )
```

### CLI Rendering

The CLI renders based on presentation type:

```
┌─ write_file ──────────────────────────────────────────────┐
│ Edit notes/report.md                                       │
├────────────────────────────────────────────────────────────┤
│ @@ -1,5 +1,7 @@                                            │
│  # Weekly Report                                           │
│                                                            │
│ -## Summary                                                │
│ +## Executive Summary                                      │
│ +                                                          │
│ +Key findings from this week:                              │
│                                                            │
│  - Completed feature X                                     │
│  - Fixed bug Y                                             │
├────────────────────────────────────────────────────────────┤
│ [y] Approve  [n] Reject  [s] Approve for session  [v] View full │
└────────────────────────────────────────────────────────────┘
```

For new files:

```
┌─ write_file ──────────────────────────────────────────────┐
│ Create notes/config.json (245 bytes)                       │
├────────────────────────────────────────────────────────────┤
│ {                                                          │
│   "version": "1.0",                                        │
│   "settings": {                                            │
│     "debug": false,                                        │
│     "timeout": 30                                          │
│   }                                                        │
│ }                                                          │
├────────────────────────────────────────────────────────────┤
│ [y] Approve  [n] Reject  [s] Approve for session           │
└────────────────────────────────────────────────────────────┘
```

For shell commands:

```
┌─ shell ───────────────────────────────────────────────────┐
│ Execute shell command                                      │
├────────────────────────────────────────────────────────────┤
│ $ git commit -m "Add weekly report"                        │
│                                                            │
│ Working directory: /home/user/project                      │
├────────────────────────────────────────────────────────────┤
│ [y] Approve  [n] Reject  [s] Approve for session           │
└────────────────────────────────────────────────────────────┘
```

### User Story: File Edit Approval with Diff

**As a** user approving file modifications
**I want** to see exactly what will change
**So that** I can catch unintended modifications before they happen

**Flow:**
1. LLM calls `write_file("src/config.py", new_content)`
2. Sandbox detects file exists, generates unified diff
3. CLI displays diff with syntax highlighting:
   - Red lines: content being removed
   - Green lines: content being added
   - Context lines for orientation
4. User reviews changes, approves or rejects
5. If approved, file is written

### User Story: Large File Handling

**As a** user approving large file writes
**I want** to see a summary with option to view full content
**So that** approval prompts don't flood my terminal

**Flow:**
1. LLM calls `write_file("data/export.json", large_content)` (10KB file)
2. Sandbox generates presentation with truncated preview
3. CLI shows first 50 lines + "[... 847 more lines]"
4. User can press `[v]` to view full content in pager
5. User approves after review

**Presentation for large content:**
```python
ApprovalPresentation(
    type="file_content",
    content=content[:2000] + f"\n\n... [{len(content) - 2000} more characters]",
    language="json",
    metadata={
        "truncated": True,
        "full_size": len(content),
        "full_content": content,  # Available for [v]iew option
    }
)
```

### User Story: Structured Data Approval

**As a** user approving API calls or complex operations
**I want** to see the structured data being sent
**So that** I can verify the payload is correct

**Example - HTTP request tool:**
```python
@requires_approval(
    presentation=lambda args: ApprovalPresentation(
        type="structured",
        content=json.dumps(args["body"], indent=2),
        language="json",
        metadata={"method": "POST", "url": args["url"]}
    )
)
def http_post(url: str, body: dict) -> dict:
    ...
```

**CLI rendering:**
```
┌─ http_post ───────────────────────────────────────────────┐
│ POST to https://api.example.com/users                      │
├────────────────────────────────────────────────────────────┤
│ {                                                          │
│   "name": "John Doe",                                      │
│   "email": "john@example.com",                             │
│   "role": "admin"                                          │
│ }                                                          │
├────────────────────────────────────────────────────────────┤
│ [y] Approve  [n] Reject                                    │
└────────────────────────────────────────────────────────────┘
```

## Updates Needed in cli_approval_user_stories.md

The CLI user stories document should be updated to reflect this architecture:

1. **Story 4 (Pre-approve known-safe tools)**: Update acceptance criteria to reference per-tool config instead of `tool_rules`:
   - Old: "set `tool_rules` (e.g., `sandbox.write` with certain sandboxes/paths)"
   - New: "set approval config in tool definition (e.g., `sandbox.paths.notes.write_approval: false`)"

2. **Story 13 (File sharing approval)**: Update to reference tool-level config:
   - Old: "If `sandbox.read` is pre-approved in tool rules"
   - New: "If `read_approval: false` is set for that sandbox path"

3. **Add new story**: Rich approval presentation
   - As an operator approving file edits, I want to see a diff of what will change
   - As an operator approving new file creation, I want to see a preview of the content
   - Acceptance criteria should reference `[v]iew full` option for large content

4. **Clarify naming**: Replace `sandbox.write`/`sandbox.read` references with actual tool names (`write_file`/`read_file`) in CLI output examples

## Open Questions

1. **Should `check_approval` be sync or async?** Some approval checks might need I/O (checking file sizes, reading existing files for diff)

2. **How to handle approval for tool batches?** If LLM calls 5 writes, prompt once or 5 times?

3. **Should OS sandbox config be explicit or always derived?** There might be cases where you want OS sandbox paths that aren't exposed as tool paths.

4. **How does this interact with MCP tools?** MCP tools come from external servers - can they declare approval requirements?

5. **How to handle binary files?** Diffs don't work for images, PDFs, etc. Show file size and type only?

6. **Should presentation generation be lazy?** Generating diffs for large files is expensive - only do it if approval is actually required and not session-cached?

7. **How does `--strict` mode interact with tool-level config?** If a path has `write_approval: false`, does `--strict` still block it? (Proposed: no, tool-level pre-approval is respected even in strict mode)
