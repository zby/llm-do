# Sandbox Architecture

**Related:** [pydanticai_contrib_sandbox.md](pydanticai_contrib_sandbox.md) for contribution plan

## Architecture Overview

The sandbox is split into two layers:

1. **FileSandbox** (reusable, potential PydanticAI contrib) — File access boundaries, query API, built-in I/O, LLM-friendly errors
2. **Sandbox** (llm-do specific) — Extends FileSandbox with network control, OS enforcement, shell tool integration

```
┌─────────────────────────────────────────────────────────────┐
│                    llm-do Sandbox                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              FileSandbox (reusable core)               │ │
│  │                                                        │ │
│  │  Boundaries:                                           │ │
│  │    readable_roots: [./portfolio, ./pipeline]           │ │
│  │    writable_roots: [./portfolio]                       │ │
│  │                                                        │ │
│  │  Query API:                                            │ │
│  │    can_read(path) → bool                               │ │
│  │    can_write(path) → bool                              │ │
│  │    resolve(path) → Path | FileSandboxError             │ │
│  │                                                        │ │
│  │  Built-in I/O:                                         │ │
│  │    read(path) → str                                    │ │
│  │    write(path, content) → None                         │ │
│  │    list_files(pattern) → List[str]                     │ │
│  │                                                        │ │
│  │  LLM-friendly errors:                                  │ │
│  │    PathNotInSandboxError, PathNotWritableError, ...    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  llm-do extensions:                                          │
│    network_enabled: bool                                     │
│    require_os_sandbox: bool                                  │
│    OS enforcement (Seatbelt/bwrap) for shell commands        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: FileSandbox (Reusable Core)

This layer can be extracted as `pydantic_ai.contrib.file_sandbox` or a standalone package.

### FileSandbox Protocol

```python
from typing import Protocol, List
from pathlib import Path

class FileSandbox(Protocol):
    """Protocol for sandboxed file operations with LLM-friendly errors.

    This is the reusable core that could be contributed to PydanticAI.
    """

    # Query API
    def can_read(self, path: str) -> bool:
        """Check if path is readable."""
        ...

    def can_write(self, path: str) -> bool:
        """Check if path is writable."""
        ...

    def resolve(self, path: str) -> Path:
        """Resolve path within sandbox. Raises FileSandboxError if outside."""
        ...

    # Built-in I/O
    def read(self, path: str, max_chars: int = 200_000) -> str:
        """Read text file from sandbox."""
        ...

    def write(self, path: str, content: str) -> None:
        """Write text file to sandbox."""
        ...

    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files matching pattern."""
        ...

    # Metadata for error messages
    @property
    def readable_roots(self) -> list[str]:
        """List of readable path roots (for error messages)."""
        ...

    @property
    def writable_roots(self) -> list[str]:
        """List of writable path roots (for error messages)."""
        ...
```

### FileSandboxConfig

```python
from pydantic import BaseModel
from typing import Literal, Optional

class PathConfig(BaseModel):
    """Configuration for a single path in the sandbox."""
    root: str
    mode: Literal["ro", "rw"] = "ro"
    suffixes: Optional[list[str]] = None      # e.g., [".md", ".pdf"]
    max_file_bytes: Optional[int] = None

class FileSandboxConfig(BaseModel):
    """Configuration for a file sandbox."""
    paths: dict[str, PathConfig]
```

### LLM-Friendly Errors

Error messages guide the LLM to correct behavior by telling it what IS allowed:

```python
class FileSandboxError(Exception):
    """Base class for sandbox errors with LLM-friendly messages."""
    pass

class PathNotInSandboxError(FileSandboxError):
    def __init__(self, path: str, readable_roots: list[str]):
        self.message = (
            f"Cannot access '{path}': path is outside sandbox.\n"
            f"Readable paths: {', '.join(readable_roots)}"
        )
        super().__init__(self.message)

class PathNotWritableError(FileSandboxError):
    def __init__(self, path: str, writable_roots: list[str]):
        self.message = (
            f"Cannot write to '{path}': path is read-only.\n"
            f"Writable paths: {', '.join(writable_roots) or 'none'}"
        )
        super().__init__(self.message)

class SuffixNotAllowedError(FileSandboxError):
    def __init__(self, path: str, allowed: list[str]):
        self.message = (
            f"Cannot access '{path}': suffix not allowed.\n"
            f"Allowed suffixes: {', '.join(allowed)}"
        )
        super().__init__(self.message)

class FileTooLargeError(FileSandboxError):
    def __init__(self, path: str, size: int, limit: int):
        self.message = (
            f"Cannot read '{path}': file too large ({size} bytes).\n"
            f"Maximum allowed: {limit} bytes"
        )
        super().__init__(self.message)
```

### FileSandboxToolset

Uses PydanticAI's `AbstractToolset` for clean integration:

```python
from pydantic_ai import RunContext
from pydantic_ai.toolsets import AbstractToolset

class FileSandboxToolset(AbstractToolset):
    """Toolset for sandboxed file operations.

    Provides read_file, write_file, and list_files tools.
    read_file handles text only; binary files should use attachments.
    """

    def __init__(self, sandbox: FileSandbox):
        self.sandbox = sandbox

    async def read_file(self, ctx: RunContext, path: str, max_chars: int = 200_000) -> str:
        """Read a text file from the sandbox.

        For binary files, use attachments instead.
        """
        return self.sandbox.read(path, max_chars=max_chars)

    async def write_file(self, ctx: RunContext, path: str, content: str) -> str:
        """Write a text file to the sandbox."""
        self.sandbox.write(path, content)
        return f"Written {len(content)} characters to {path}"

    async def list_files(self, ctx: RunContext, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files in the sandbox matching a glob pattern."""
        return self.sandbox.list_files(path, pattern)
```

---

## Layer 2: llm-do Sandbox (Extended)

llm-do extends FileSandbox with additional features:

### SandboxConfig (extends FileSandboxConfig)

```python
class SandboxConfig(FileSandboxConfig):
    """Extended configuration for llm-do sandbox."""
    network: bool = False                    # network access control
    require_os_sandbox: bool = False         # fail if OS sandbox unavailable
```

### Sandbox Class

```python
from .file_sandbox import FileSandbox, FileSandboxConfig

class Sandbox(FileSandbox):
    """Extended sandbox with llm-do specific features."""

    def __init__(self, config: SandboxConfig):
        super().__init__(config)
        self.network_enabled = config.network
        self.require_os_sandbox = config.require_os_sandbox
```

### Worker Definition

```yaml
# workers/example.yaml
sandbox:
  paths:
    portfolio:
      root: ./portfolio
      mode: rw
      suffixes: [.md, .pdf]
      max_file_bytes: 10000000
    pipeline:
      root: ./pipeline
      mode: ro
  network: false
  require_os_sandbox: false
```

---

## FileSandbox vs Tools vs Approvals

Three separate concepts (only FileSandbox is reusable):

| Concept | Layer | What it controls |
|---------|-------|------------------|
| **FileSandbox** | Reusable | File access boundaries, query API, built-in I/O |
| **Sandbox** | llm-do | Extends FileSandbox with network, OS enforcement |
| **Tools** | llm-do | What the LLM can call (shell, worker_call, etc.) |
| **Approvals** | llm-do | What needs user confirmation |

They are orthogonal:
- A tool can be available but sandbox blocks its effect
- A tool can be approved but sandbox still restricts it
- Sandbox boundaries are fixed; approvals don't change them **(initial design for simplicity)**

---

## OS Sandbox (llm-do Specific)

### Important Limitation: Subprocess Only

**OS sandboxing only applies to shell commands (subprocesses), not to Python file I/O.**

```
┌───────────────────────────────────────────────┐
│ Python process (NOT OS-sandboxed)             │
│                                               │
│  sandbox.read()  → Python validation only     │
│  sandbox.write() → Python validation only     │
│                                               │
│  shell(cmd) ──────┬───────────────────────────┤
└───────────────────┼───────────────────────────┘
                    ▼
            ┌───────────────────┐
            │ OS Sandbox        │
            │ (Seatbelt/bwrap)  │
            │                   │
            │ Subprocess only   │
            └───────────────────┘
```

**What's OS-enforced vs application-enforced:**

| Operation | OS-enforced | Application-enforced |
|-----------|-------------|---------------------|
| `sandbox.read()` | No | Python validation |
| `sandbox.write()` | No | Python validation |
| `shell()` path access | Seatbelt/bwrap | (optional pre-check) |
| `shell()` network | Seatbelt/bwrap | — |
| File suffixes | — | Python validation |
| File size limits | — | Python validation |

### macOS: Apple Seatbelt

```python
def create_seatbelt_policy(sandbox_config: SandboxConfig) -> str:
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
def create_bwrap_args(sandbox_config: SandboxConfig) -> list[str]:
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

```python
if not os_sandbox_available():
    if sandbox_config.require_os_sandbox:
        raise SecurityError("OS sandbox required but unavailable")
    logger.warning("OS sandbox unavailable, application-level only")
```

---

## Shell Tool Error Enhancement (llm-do Specific)

When OS sandbox blocks a shell command, enhance errors with sandbox context:

```python
def shell(command: str, sandbox: Sandbox, ...) -> ShellResult:
    result = subprocess.run(...)

    if result.returncode != 0:
        if "Permission denied" in result.stderr:
            result.stderr += (
                f"\n\nNote: This worker's writable paths are: "
                f"{', '.join(sandbox.writable_roots)}"
            )
        if "Network is unreachable" in result.stderr:
            result.stderr += (
                "\n\nNote: Network access is disabled for this worker."
            )

    return ShellResult(...)
```

---

## Integration with Runtime Architecture

### Updated Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    protocols.py                              │
│  - WorkerDelegator    (existing)                            │
│  - WorkerCreator      (existing)                            │
│  - FileSandbox        (reusable protocol)                   │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ (implements)
                         │
┌────────────────────────┴────────────────────────────────────┐
│                 file_sandbox.py (reusable)                   │
│  - FileSandbox implementation                                │
│  - FileSandboxConfig, PathConfig                             │
│  - FileSandboxError classes                                  │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ (extends)
                         │
┌────────────────────────┴────────────────────────────────────┐
│                    sandbox.py (llm-do)                       │
│  - Sandbox (extends FileSandbox)                             │
│  - SandboxConfig (extends FileSandboxConfig)                 │
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

### Dependency Flow

```
protocols.py          ← defines FileSandbox protocol (no deps)
       ↑
file_sandbox.py       ← implements FileSandbox (reusable)
       ↑
sandbox.py            ← extends with network, OS enforcement
       ↑
tools.py              ← uses FileSandbox protocol
       ↑
execution.py          ← wraps with OS sandbox
       ↑
runtime.py            ← creates Sandbox, wires everything
```

Key: `tools.py` depends on `FileSandbox` protocol (interface), not `Sandbox` (implementation). No circular imports.

---

## Static vs Dynamic Permissions

### Initial Design: Static (for simplicity)

Sandbox boundaries are fixed at worker startup:
- Defined in worker YAML
- Cannot be changed by approvals
- Commands exceeding boundaries fail

This is a deliberate simplification for the initial implementation.

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

---

## Attachment Handling

Attachments are files passed to sub-workers. They must come from sandbox:

```python
def load_attachment(path: str, sandbox: FileSandbox) -> AttachmentPayload:
    resolved = sandbox.resolve(path)  # raises if outside
    return AttachmentPayload(path=resolved, ...)
```

---

## Worker Delegation

When a worker calls another worker:

```python
def worker_call(worker_name: str, attachments: list[str] = None):
    # Attachments must be in caller's sandbox
    if attachments:
        for path in attachments:
            caller_sandbox.resolve(path)  # validates access

    # Child worker uses its OWN sandbox (from its definition)
    child_sandbox = load_worker(worker_name).sandbox
```

**Key principle:** Child workers have their own sandbox.

---

## Migration Path

### Phase 1: Implement FileSandbox (reusable core)
1. Create `file_sandbox.py` with `FileSandbox` implementation
2. Add `FileSandboxConfig`, `PathConfig`
3. Add error classes with LLM-friendly messages
4. Unit tests for all operations

### Phase 2: Implement Sandbox (llm-do extension)
1. Create `sandbox.py` extending `FileSandbox`
2. Add `SandboxConfig` with `network`, `require_os_sandbox`
3. Add OS enforcement (Seatbelt, bwrap)

### Phase 3: Integrate with tools and runtime
1. Update `tools.py` to use `FileSandbox` protocol
2. Update `runtime.py` to create and inject `Sandbox`
3. Update `execution.py` for OS enforcement

### Phase 4: Consider upstream contribution
1. Extract `file_sandbox.py` to separate package or PydanticAI contrib
2. llm-do depends on extracted package
3. `Sandbox` extends contributed `FileSandbox`

---

## Resolved Design Decisions

| Issue | Decision |
|-------|----------|
| Reusable vs llm-do specific | FileSandbox (file boundaries, query API, I/O, errors) is reusable. Network, OS enforcement, shell rules are llm-do specific. |
| OS sandbox scope | Subprocess only (shell commands). Python I/O uses application validation. |
| Network blocking | Shell commands only. Python HTTP not blocked. |
| Nested worker sandboxes | Each worker has own Sandbox instance. OS enforcement inherits from parent process. |
| Shell rules vs tool_rules | tool_rules gates availability; shell_rules overrides approval per-pattern. |
| Shell working directory | Project root (registry.root), not sandbox-specific. |
| Toolset approach | Use `AbstractToolset` for FileSandboxToolset. |
| Binary file handling | `read()` handles text only. Binary files use attachments. |

---

## Open Questions

1. **Contrib vs standalone:** Publish as `pydantic-ai-file-sandbox` on PyPI, or propose to PydanticAI contrib?

2. **Async support:** Should methods be async or sync?

3. **Network granularity:** Allow specific hosts/ports instead of binary on/off?
