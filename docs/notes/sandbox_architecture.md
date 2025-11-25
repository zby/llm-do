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
- Sandbox boundaries are fixed; approvals don't change them

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

Approval doesn't grant network access. Sandbox boundaries are static.

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

### Current Design: Static

Sandbox boundaries are fixed at worker startup:
- Defined in worker YAML
- Cannot be changed by approvals
- Commands exceeding boundaries fail

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

## Migration from Current System

### Phase 1: Refactor Config
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
```

### Phase 2: Add Query API
- Implement `can_read()`, `can_write()`, `resolve()`
- Tools use query API for validation

### Phase 3: OS Enforcement
- Implement Seatbelt wrapper (macOS)
- Implement bwrap wrapper (Linux)
- Wrap worker execution

### Phase 4: Rename Tools
- `sandbox_read_text` → `read`
- `sandbox_write_text` → `write`
- `sandbox_list` → `list_files`

---

## Open Questions

1. **Tmpdir:** Always writable, or explicit in config?

2. **Home directory:** Allow `~/.cache`, `~/.config`?

3. **Child sandbox inheritance:** Should children be restricted to subset of parent?

4. **Dynamic grants:** When to implement, if ever?

5. **Network granularity:** Allow specific hosts/ports instead of binary on/off?
