# Sandbox Architecture

## What is a Sandbox

A sandbox is an **execution environment** with:
1. **Boundaries** — which paths are readable/writable, network access
2. **Query API** — tools can ask "can I access this path?"
3. **Built-in I/O** — read, write, list operations
4. **OS enforcement** — kernel-level restrictions (defense in depth)

```
┌─────────────────────────────────────────────┐
│ Sandbox                                     │
│                                             │
│  Boundaries:                                │
│    readable: [./portfolio, ./pipeline]      │
│    writable: [./portfolio]                  │
│    network: false                           │
│                                             │
│  Query API:                                 │
│    can_read(path) → bool                    │
│    can_write(path) → bool                   │
│    resolve(path) → Path | Error             │
│                                             │
│  Built-in Tools:                            │
│    read(path) → str                         │
│    write(path, content) → None              │
│    list(pattern) → List[str]                │
│                                             │
└─────────────────────────────────────────────┘
         ↑
         │ Tools operate within sandbox
         │
    ┌────┴────┐
    │  shell  │  ← can query sandbox, OS enforces boundaries
    └─────────┘
```

---

## Sandbox vs Tools vs Approvals

Three separate concepts:

| Concept | What it is | What it controls |
|---------|------------|------------------|
| **Sandbox** | Execution environment | What CAN happen (paths, network) |
| **Tools** | Capabilities exposed to LLM | What the LLM CAN call |
| **Approvals** | UX layer | What NEEDS user confirmation |

They are orthogonal:
- A tool can be available but sandbox blocks its effect
- A tool can be approved but sandbox still restricts it
- Sandbox boundaries are fixed; approvals don't change them **(initial design for simplicity)**

**Example:**
```yaml
sandbox:
  paths:
    portfolio: { root: ./portfolio, mode: rw }
  network: false  # fixed boundary

tools:
  - shell  # available to LLM

tool_rules:
  shell:
    approval_required: true  # UX: user sees commands
```

If LLM runs `curl http://example.com`:
1. Tool is available ✓
2. User approves ✓
3. Sandbox blocks network ✗ → command fails

**Initial design:** Approval doesn't grant network access. Sandbox boundaries are static. See "Static vs Dynamic Permissions" for future extension options.

---

## Sandbox Configuration

```yaml
sandbox:
  # Path boundaries
  paths:
    portfolio:
      root: ./portfolio
      mode: rw                    # read-write
      suffixes: [.md, .pdf]       # application-level filter
      max_file_bytes: 10000000    # application-level limit
    pipeline:
      root: ./pipeline
      mode: ro                    # read-only
      suffixes: [.pdf]
    framework:
      root: ./framework
      mode: ro

  # Network boundary
  network: false

  # OS sandbox requirement
  require_os_sandbox: false  # warn if unavailable, or fail?
```

**What's OS-enforced vs application-enforced:**

| Boundary | OS-enforced | Application-enforced |
|----------|-------------|---------------------|
| Path read/write | ✓ Seatbelt/bwrap | ✓ Python validation |
| Network access | ✓ Seatbelt/bwrap | — |
| File suffixes | — | ✓ Python validation |
| File size limits | — | ✓ Python validation |

OS enforcement is the security boundary. Application enforcement adds fine-grained policies.

---

## Sandbox Query API

Tools can ask the sandbox about permissions before acting:

```python
class Sandbox:
    def can_read(self, path: str) -> bool:
        """Check if path is within readable boundaries."""

    def can_write(self, path: str) -> bool:
        """Check if path is within writable boundaries."""

    def resolve(self, path: str) -> Path:
        """Resolve path within sandbox. Raises if outside boundaries."""

    def check_suffix(self, path: Path) -> None:
        """Raises if suffix not allowed (application policy)."""

    def check_size(self, path: Path) -> None:
        """Raises if file exceeds size limit (application policy)."""
```

**Why tools should query:**
- Clear error messages: "path outside sandbox" vs generic failure
- Pre-flight validation before expensive operations
- Pattern rules can use `can_read`/`can_write` for path validation

**Why OS enforcement is still needed:**
- Tools might have bugs
- Defense in depth
- Shell commands can't be pre-validated completely

---

## Error Handling and LLM Guidance

When sandbox rejects an operation, errors must guide the LLM to correct behavior:

**Bad error (unhelpful):**
```
Error: Permission denied
```

**Good error (actionable):**
```
Cannot read '/etc/passwd': path is outside sandbox.
Readable paths: ./portfolio, ./pipeline, ./framework
```

**Error messages should include:**

| Rejection reason | Error should include |
|------------------|---------------------|
| Path outside sandbox | List of accessible paths |
| Write to read-only path | Which paths ARE writable |
| Suffix not allowed | List of allowed suffixes |
| File too large | Size limit and actual size |
| Network blocked | "Network access is disabled for this worker" |

**Implementation:**

```python
class SandboxError(Exception):
    """Base class for sandbox errors with LLM-friendly messages."""
    pass

class PathNotInSandboxError(SandboxError):
    def __init__(self, path: str, sandbox: 'Sandbox'):
        readable = [p.root for p in sandbox.paths.values()]
        self.message = (
            f"Cannot access '{path}': path is outside sandbox.\n"
            f"Readable paths: {', '.join(readable)}"
        )
        super().__init__(self.message)

class PathNotWritableError(SandboxError):
    def __init__(self, path: str, sandbox: 'Sandbox'):
        writable = [p.root for p in sandbox.paths.values() if p.mode == 'rw']
        self.message = (
            f"Cannot write to '{path}': path is read-only.\n"
            f"Writable paths: {', '.join(writable) or 'none'}"
        )
        super().__init__(self.message)

class SuffixNotAllowedError(SandboxError):
    def __init__(self, path: str, allowed: List[str]):
        self.message = (
            f"Cannot access '{path}': suffix not allowed.\n"
            f"Allowed suffixes: {', '.join(allowed)}"
        )
        super().__init__(self.message)

class FileTooLargeError(SandboxError):
    def __init__(self, path: str, size: int, limit: int):
        self.message = (
            f"Cannot read '{path}': file too large ({size} bytes).\n"
            f"Maximum allowed: {limit} bytes"
        )
        super().__init__(self.message)
```

**For shell commands:**

When OS sandbox blocks a shell command, the error is less specific (just "permission denied" or "network unreachable"). The shell tool should wrap these:

```python
def shell(command: str, ...) -> ShellResult:
    result = subprocess.run(...)

    if result.returncode != 0:
        # Enhance error with sandbox context
        if "Permission denied" in result.stderr:
            result.stderr += (
                f"\n\nNote: This worker's writable paths are: "
                f"{', '.join(sandbox.writable_paths)}"
            )
        if "Network is unreachable" in result.stderr:
            result.stderr += (
                "\n\nNote: Network access is disabled for this worker."
            )

    return ShellResult(...)
```

This helps the LLM understand WHY something failed and WHAT it can do instead.

---

## Sandbox Built-in Tools

The sandbox provides basic I/O as built-in tools:

```python
# Exposed to LLM as tools
def read(path: str, max_chars: int = 200_000) -> str:
    """Read text file from sandbox."""
    resolved = sandbox.resolve(path)
    sandbox.check_suffix(resolved)
    sandbox.check_size(resolved)
    return resolved.read_text()[:max_chars]

def write(path: str, content: str) -> None:
    """Write text file to sandbox."""
    resolved = sandbox.resolve(path)
    sandbox.check_suffix(resolved)
    # OS sandbox also enforces write permission
    resolved.write_text(content)

def list_files(path: str = ".", pattern: str = "**/*") -> List[str]:
    """List files in sandbox matching pattern."""
    resolved = sandbox.resolve(path)
    return [str(p.relative_to(resolved)) for p in resolved.glob(pattern)]
```

**Naming:**
- Current: `sandbox_read_text`, `sandbox_write_text`, `sandbox_list`
- Proposed: `read`, `write`, `list_files` (sandbox is implicit context)

---

## External Tools Using Sandbox

Tools like `shell` operate within the sandbox but aren't part of it:

```python
def shell(command: str, timeout: int = 30) -> ShellResult:
    """Execute shell command within sandbox boundaries."""
    args = shlex.split(command)

    # Tool can query sandbox for validation (optional, for better errors)
    # But OS sandbox enforces regardless

    result = subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        cwd=sandbox.root,
        # OS sandbox restricts filesystem and network
    )

    return ShellResult(
        stdout=result.stdout.decode()[:50000],
        stderr=result.stderr.decode()[:50000],
        exit_code=result.returncode,
    )
```

The shell tool doesn't need to validate every path in the command—the OS sandbox enforces boundaries. But it CAN query the sandbox for better error messages.

---

## OS Sandbox Implementation

### macOS: Apple Seatbelt

```python
def create_seatbelt_policy(sandbox_config) -> str:
    writable = [p.root for p in sandbox_config.paths.values() if p.mode == 'rw']

    policy = """
(version 1)
(deny default)
(allow file-read*)
"""
    for path in writable:
        policy += f'(allow file-write* (subpath "{path}"))\n'

    if not sandbox_config.network:
        policy += "(deny network*)\n"

    policy += """
(allow process-fork)
(allow process-exec)
"""
    return policy
```

### Linux: bubblewrap

```python
def create_bwrap_args(sandbox_config) -> List[str]:
    args = ["bwrap"]

    for name, path_config in sandbox_config.paths.items():
        if path_config.mode == 'rw':
            args.extend(["--bind", path_config.root, path_config.root])
        else:
            args.extend(["--ro-bind", path_config.root, path_config.root])

    if not sandbox_config.network:
        args.append("--unshare-net")

    args.extend(["--die-with-parent", "--"])
    return args
```

### Fallback

When OS sandbox is unavailable:
```python
if not os_sandbox_available():
    if sandbox_config.require_os_sandbox:
        raise SecurityError("OS sandbox required but unavailable")
    logger.warning("OS sandbox unavailable, application-level only")
```

---

## Static vs Dynamic Permissions

### Initial Design: Static (for simplicity)

Sandbox boundaries are fixed at worker startup:
- Defined in worker YAML
- Cannot be changed by approvals
- Commands exceeding boundaries fail

This is a deliberate simplification for the initial implementation. It keeps the mental model simple and makes security auditing straightforward.

### Future Option: Dynamic Grants

Approvals could grant temporary permissions:
```yaml
# FUTURE - not implemented
shell_rules:
  - pattern: "git push"
    approval_required: true
    grants:
      network: true  # if approved, enable network for this command
```

**Why start static:**
1. Simpler mental model
2. Easier to audit (permissions in YAML)
3. Less attack surface
4. Forces explicit configuration

**When dynamic might help:**
- Occasional network operations (git push, API calls)
- Interactive workflows
- Reducing config duplication

---

## Attachment Handling

Attachments are files passed to sub-workers. They must come from sandbox:

```python
def load_attachment(path: str) -> AttachmentPayload:
    # Must be readable in current sandbox
    resolved = sandbox.resolve(path)  # raises if outside

    # Check attachment policy (count, size, suffix)
    attachment_policy.validate(resolved)

    return AttachmentPayload(path=resolved, ...)
```

The sandbox's `resolve()` ensures attachments can only come from readable paths.

---

## Worker Delegation

When a worker calls another worker:

```python
def worker_call(worker_name: str, attachments: List[str] = None):
    # Attachments must be in caller's sandbox
    if attachments:
        for path in attachments:
            caller_sandbox.resolve(path)  # validates access

    # Child worker uses its OWN sandbox (from its definition)
    child_sandbox = load_worker(worker_name).sandbox

    # Child cannot exceed parent's attachment access
    # (attachments are pre-resolved absolute paths)
```

**Key principle:** Child workers have their own sandbox. They cannot access paths outside their sandbox, even if parent could.

---

## Integration with Runtime Architecture

The sandbox design must integrate with the existing DI-based runtime (see [runtime_refactor_with_di.md](runtime_refactor_with_di.md)).

### Current Architecture

```
protocols.py     → WorkerDelegator, WorkerCreator
tools.py         → register_worker_tools (depends on protocols)
approval.py      → ApprovalController
execution.py     → agent runners
runtime.py       → orchestrates, implements protocols
```

### Adding SandboxProtocol

Add `SandboxProtocol` to `protocols.py` so tools depend on interface, not implementation:

```python
# protocols.py

class SandboxProtocol(Protocol):
    """Protocol for sandbox operations.

    Tools depend on this protocol, not concrete Sandbox implementation.
    This enables testing with mock sandboxes and breaks circular deps.
    """

    # Query API
    def can_read(self, path: str) -> bool:
        """Check if path is readable."""
        ...

    def can_write(self, path: str) -> bool:
        """Check if path is writable."""
        ...

    def resolve(self, path: str) -> Path:
        """Resolve path within sandbox. Raises SandboxError if outside."""
        ...

    # Built-in I/O
    def read(self, path: str, max_chars: int = 200_000) -> str:
        """Read text file from sandbox."""
        ...

    def write(self, path: str, content: str) -> None:
        """Write text file to sandbox."""
        ...

    def list_files(self, path: str = ".", pattern: str = "**/*") -> List[str]:
        """List files matching pattern."""
        ...

    # Metadata for error messages
    @property
    def readable_paths(self) -> List[str]:
        """List of readable path roots (for error messages)."""
        ...

    @property
    def writable_paths(self) -> List[str]:
        """List of writable path roots (for error messages)."""
        ...

    @property
    def network_enabled(self) -> bool:
        """Whether network access is allowed."""
        ...
```

### Updated Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    protocols.py                              │
│  - WorkerDelegator    (existing)                            │
│  - WorkerCreator      (existing)                            │
│  - SandboxProtocol    (NEW)                                 │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ (implements)
                         │
┌────────────────────────┴────────────────────────────────────┐
│                     sandbox.py                               │
│  - Sandbox class (implements SandboxProtocol)               │
│  - SandboxError classes                                     │
│  - OS enforcement wrappers (Seatbelt, bwrap)                │
└─────────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ tools.py │   │execution │   │ runtime  │
    │          │   │   .py    │   │   .py    │
    │ register │   │          │   │          │
    │ _sandbox │   │ OS wrap  │   │ creates  │
    │ _tools() │   │ here     │   │ Sandbox  │
    └──────────┘   └──────────┘   └──────────┘
```

### Where Tools Are Registered

Update `tools.py` to use `SandboxProtocol`:

```python
# tools.py

from .protocols import SandboxProtocol, WorkerDelegator, WorkerCreator

def register_worker_tools(
    agent: Agent,
    context: WorkerContext,
    delegator: WorkerDelegator,
    creator: WorkerCreator,
    sandbox: SandboxProtocol,  # NEW parameter
) -> None:
    """Register all tools for a worker."""

    # Sandbox built-in tools (use protocol methods)
    @agent.tool(name="read", description="Read text file")
    def read_tool(ctx: RunContext, path: str) -> str:
        return sandbox.read(path)

    @agent.tool(name="write", description="Write text file")
    def write_tool(ctx: RunContext, path: str, content: str) -> None:
        sandbox.write(path, content)

    @agent.tool(name="list_files", description="List files")
    def list_tool(ctx: RunContext, path: str = ".", pattern: str = "**/*") -> List[str]:
        return sandbox.list_files(path, pattern)

    # Shell tool (queries sandbox for error context)
    @agent.tool(name="shell", description="Execute shell command")
    def shell_tool(ctx: RunContext, command: str) -> ShellResult:
        return execute_shell(command, sandbox)

    # Worker delegation (existing)
    # ...
```

### Where OS Enforcement Hooks In

OS sandbox wraps the entire worker execution in `execution.py`:

```python
# execution.py

from .sandbox import Sandbox, create_os_sandbox

async def default_agent_runner_async(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
    *,
    register_tools_fn: Callable,
    sandbox: Sandbox,  # NEW parameter
) -> tuple[Any, List[Any]]:
    """Async agent runner with OS sandbox enforcement."""

    # Wrap entire execution in OS sandbox
    with create_os_sandbox(sandbox.config):
        exec_ctx = prepare_agent_execution(...)
        agent = Agent(**exec_ctx.agent_kwargs)
        register_tools_fn(agent, context)

        run_result = await agent.run(...)

    return (run_result.output, messages)
```

### Runtime Creates Sandbox

In `runtime.py`, create the `Sandbox` instance and inject it:

```python
# runtime.py

from .sandbox import Sandbox
from .protocols import SandboxProtocol

async def run_worker_async(...) -> WorkerRunResult:
    definition = registry.load_definition(worker)

    # Create sandbox from worker definition
    sandbox = Sandbox(definition.sandbox)

    # Create protocol implementations for DI
    delegator = RuntimeDelegator(context)
    creator = RuntimeCreator(context)

    # Tool registration with sandbox injection
    def register_tools_for_worker(agent, ctx):
        register_worker_tools(agent, ctx, delegator, creator, sandbox)

    # Run with OS enforcement
    result = await default_agent_runner_async(
        definition, input_data, context, output_model,
        register_tools_fn=register_tools_for_worker,
        sandbox=sandbox,
    )

    return WorkerRunResult(...)
```

### Dependency Flow (No Circular Imports)

```
protocols.py          ← defines SandboxProtocol (no deps)
       ↑
sandbox.py            ← implements SandboxProtocol
       ↑
tools.py              ← uses SandboxProtocol (not Sandbox)
       ↑
execution.py          ← wraps with OS sandbox
       ↑
runtime.py            ← creates Sandbox, wires everything
```

Key: `tools.py` depends on `SandboxProtocol` (interface), not `Sandbox` (implementation). No circular imports.

---

## Migration from Current System

### Phase 1: Add SandboxProtocol
1. Add `SandboxProtocol` to `protocols.py`
2. Keep existing `SandboxManager`/`SandboxToolset` working
3. No behavior changes yet

### Phase 2: Implement Sandbox Class
1. Create new `Sandbox` class implementing `SandboxProtocol`
2. Include query API: `can_read()`, `can_write()`, `resolve()`
3. Include built-in I/O: `read()`, `write()`, `list_files()`
4. Include LLM-friendly error classes

### Phase 3: Refactor Config
```yaml
# Before (multiple sandboxes)
sandboxes:
  portfolio:
    path: ./portfolio
    mode: rw

# After (single sandbox with paths)
sandbox:
  paths:
    portfolio:
      root: ./portfolio
      mode: rw
  network: false
```

### Phase 4: Update tools.py
1. Add `sandbox: SandboxProtocol` parameter to `register_worker_tools()`
2. Replace `sandbox_*` tools with calls to `sandbox.read()`, etc.
3. Add shell tool using sandbox for error context

### Phase 5: Update runtime.py
1. Create `Sandbox` instance from worker definition
2. Inject sandbox into `register_worker_tools()`
3. Pass sandbox to agent runner

### Phase 6: OS Enforcement
1. Implement `create_os_sandbox()` context manager
2. Add Seatbelt wrapper (macOS)
3. Add bwrap wrapper (Linux)
4. Wrap agent execution in `execution.py`

### Phase 7: Rename Tools
- `sandbox_read_text` → `read`
- `sandbox_write_text` → `write`
- `sandbox_list` → `list_files`
- Deprecate old names with warnings

---

## Open Questions

1. **Tmpdir:** Always writable, or explicit in config?

2. **Home directory:** Allow `~/.cache`, `~/.config`?

3. **Child sandbox inheritance:** Should children be restricted to subset of parent?

4. **Dynamic grants:** When to implement, if ever?

5. **Network granularity:** Allow specific hosts/ports instead of binary on/off?
