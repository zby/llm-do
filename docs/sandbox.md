# Sandbox Architecture

The sandbox system provides secure file access boundaries for workers.

## Two-Layer Architecture

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
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

1. **FileSandbox** (reusable core) — File access boundaries, query API, built-in I/O, LLM-friendly errors
2. **Sandbox** (llm-do specific) — Extends FileSandbox with network control and OS enforcement hooks

---

## FileSandbox Protocol

```python
from typing import Protocol
from pathlib import Path

class FileSandbox(Protocol):
    """Protocol for sandboxed file operations with LLM-friendly errors."""

    # Query API
    def can_read(self, path: str) -> bool: ...
    def can_write(self, path: str) -> bool: ...
    def resolve(self, path: str) -> Path: ...

    # Built-in I/O
    def read(self, path: str, max_chars: int = 20_000, offset: int = 0) -> ReadResult: ...
    def write(self, path: str, content: str) -> None: ...
    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]: ...

    # Metadata for error messages
    @property
    def readable_roots(self) -> list[str]: ...
    @property
    def writable_roots(self) -> list[str]: ...
```

---

## Configuration

### PathConfig

```python
class PathConfig(BaseModel):
    """Configuration for a single path in the sandbox."""
    root: str
    mode: Literal["ro", "rw"] = "ro"
    suffixes: Optional[list[str]] = None      # e.g., [".md", ".pdf"]
    max_file_bytes: Optional[int] = None
```

### FileSandboxConfig

```python
class FileSandboxConfig(BaseModel):
    """Configuration for a file sandbox."""
    paths: dict[str, PathConfig]
```

### SandboxConfig (llm-do extension)

```python
class SandboxConfig(FileSandboxConfig):
    """Extended configuration for llm-do sandbox."""
    network: bool = False
    require_os_sandbox: bool = False
```

### Worker Definition Example

```yaml
# workers/example.worker
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

## Error Classes

Error messages guide the LLM to correct behavior by telling it what IS allowed:

```python
class FileSandboxError(Exception):
    """Base class for sandbox errors with LLM-friendly messages."""

class PathNotInSandboxError(FileSandboxError):
    # Message: "Cannot access '{path}': path is outside sandbox.
    #           Readable paths: {readable_roots}"

class PathNotWritableError(FileSandboxError):
    # Message: "Cannot write to '{path}': path is read-only.
    #           Writable paths: {writable_roots}"

class SuffixNotAllowedError(FileSandboxError):
    # Message: "Cannot access '{path}': suffix not allowed.
    #           Allowed suffixes: {allowed}"

class FileTooLargeError(FileSandboxError):
    # Message: "Cannot read '{path}': file too large ({size} bytes).
    #           Maximum allowed: {limit} bytes"
```

---

## Tools

The sandbox provides three tools to workers:

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read text file from sandbox |
| `write_file(path, content)` | Write text file to sandbox |
| `list_files(path, pattern)` | List files matching glob pattern |

Legacy tool names (`sandbox_read_text`, `sandbox_write_text`, `sandbox_list`) are supported for backward compatibility.

---

## Concepts

### FileSandbox vs Tools vs Approvals

| Concept | What it controls |
|---------|------------------|
| **FileSandbox** | File access boundaries, query API, built-in I/O |
| **Sandbox** | Extends FileSandbox with network, OS enforcement |
| **Tools** | What the LLM can call (shell, worker_call, etc.) |
| **Approvals** | What needs user confirmation |

They are orthogonal:
- A tool can be available but sandbox blocks its effect
- A tool can be approved but sandbox still restricts it
- Sandbox boundaries are fixed at worker startup

### OS Sandbox Scope

**OS sandboxing only applies to shell commands (subprocesses), not to Python file I/O.**

| Operation | OS-enforced | Application-enforced |
|-----------|-------------|---------------------|
| `sandbox.read()` | No | Python validation |
| `sandbox.write()` | No | Python validation |
| `shell()` path access | Seatbelt/bwrap | Optional pre-check |
| `shell()` network | Seatbelt/bwrap | — |
| File suffixes | — | Python validation |
| File size limits | — | Python validation |

### Worker Delegation

When a worker calls another worker:
- Attachments must be in caller's sandbox
- Attachments are validated against `attachment_policy` (count, size, suffixes)
- Attachments can require `sandbox.read` approval before sharing
- Child worker uses its OWN sandbox (from its definition)

```python
def worker_call(worker_name: str, attachments: list[str] = None):
    # 1. Attachments validated against caller's sandbox
    # 2. AttachmentPolicy enforced (count, bytes, suffixes)
    # 3. sandbox.read approval checked (if configured)
    # 4. Child worker uses its own sandbox config
```

To require approval for sharing files with delegated workers:

```yaml
tool_rules:
  sandbox.read:
    allowed: true
    approval_required: true  # User approves each attachment
```

See [worker_delegation.md](worker_delegation.md) for full details.

---

## Module Structure

```
llm_do/
├── protocols.py      # FileSandbox protocol
├── filesystem_sandbox.py   # FileSandboxImpl, config, errors
├── sandbox_v2.py     # Sandbox extending FileSandbox
├── tools.py          # Tool registration using FileSandbox
└── runtime.py        # Creates Sandbox, injects into tools
```

Dependency flow:
```
protocols.py      ← defines FileSandbox protocol (no deps)
       ↑
filesystem_sandbox.py   ← implements FileSandbox
       ↑
sandbox_v2.py     ← extends with network, OS enforcement
       ↑
tools.py          ← uses FileSandbox protocol
       ↑
runtime.py        ← creates Sandbox, wires everything
```

Key: `tools.py` depends on `FileSandbox` protocol (interface), not `Sandbox` (implementation). No circular imports.
