# PydanticAI Contrib: File Sandbox

**Status:** Planning
**Context:** Feedback on potentially contributing sandbox functionality to PydanticAI
**Related:** [sandbox_architecture.md](sandbox_architecture.md), [sandbox_implementation_plan.md](sandbox_implementation_plan.md)

## Summary of Feedback

The sandbox design can be split into:

1. **Reusable for PydanticAI contrib** - File sandbox + query API + LLM-friendly errors
2. **Keep in llm-do** - Approvals, OS sandboxing, YAML config, worker lifecycle

---

## What Maps to PydanticAI

### Good Fit: FileSandbox Protocol + Toolset

PydanticAI already has:
- **Dependencies** - inject arbitrary objects via `deps_type`
- **Toolsets** - `AbstractToolset` for groups of tools

Our design fits naturally:

```python
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext, tool

@dataclass
class SandboxDeps:
    sandbox: FileSandbox  # query API object

agent = Agent(
    model="...",
    deps_type=SandboxDeps,
)

@tool
def read_file(ctx: RunContext[SandboxDeps], path: str) -> str:
    return ctx.deps.sandbox.read(path)
```

### Good Fit: LLM-Friendly Errors

Error messages that tell the LLM what IS allowed:

```
Cannot read '/etc/passwd': path is outside sandbox.
Readable paths: ./portfolio, ./pipeline
```

This aligns with PydanticAI's philosophy and is generally useful.

---

## What Should Stay in llm-do

| Component | Why it's llm-do specific |
|-----------|-------------------------|
| **Approvals** | UX assumptions (CLI, sessions), policy model |
| **OS Sandbox** | Infra-specific (Seatbelt, bwrap), external binaries |
| **YAML Config** | llm-do worker definitions, not PydanticAI's Python-first approach |
| **Static/Dynamic Permissions** | Tied to approval policies |

---

## Proposed Split

### `pydantic_ai.contrib.file_sandbox` (Upstream)

Minimal, reusable API:

```python
# protocols.py
class FileSandbox(Protocol):
    """Protocol for sandboxed file operations with LLM-friendly errors."""

    def can_read(self, path: str) -> bool:
        """Check if path is readable."""
        ...

    def can_write(self, path: str) -> bool:
        """Check if path is writable."""
        ...

    def resolve(self, path: str) -> Path:
        """Resolve path within sandbox. Raises FileSandboxError if outside."""
        ...

    def read(self, path: str, max_chars: int = 200_000) -> str:
        """Read text file from sandbox."""
        ...

    def write(self, path: str, content: str) -> None:
        """Write text file to sandbox."""
        ...

    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files matching pattern."""
        ...

    @property
    def readable_roots(self) -> list[str]:
        """List of readable path roots (for error messages)."""
        ...

    @property
    def writable_roots(self) -> list[str]:
        """List of writable path roots (for error messages)."""
        ...
```

```python
# config.py
from pydantic import BaseModel
from typing import Literal, Optional

class PathConfig(BaseModel):
    """Configuration for a single path in the sandbox."""
    root: str
    mode: Literal["ro", "rw"] = "ro"
    suffixes: Optional[list[str]] = None
    max_file_bytes: Optional[int] = None

class FileSandboxConfig(BaseModel):
    """Configuration for a file sandbox."""
    paths: dict[str, PathConfig]
```

```python
# errors.py
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

```python
# sandbox.py
class FileSandbox:
    """A sandboxed file system with LLM-friendly error messages."""

    def __init__(self, config: FileSandboxConfig):
        self.config = config
        self._setup_paths()

    def can_read(self, path: str) -> bool: ...
    def can_write(self, path: str) -> bool: ...
    def resolve(self, path: str) -> Path: ...
    def read(self, path: str, max_chars: int = 200_000) -> str: ...
    def write(self, path: str, content: str) -> None: ...
    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]: ...

    @property
    def readable_roots(self) -> list[str]: ...

    @property
    def writable_roots(self) -> list[str]: ...
```

```python
# toolset.py
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

### `llm-do` (Keep Here)

Everything else stays in llm-do:

```python
# llm_do/sandbox.py - extends contrib
from pydantic_ai.contrib.file_sandbox import FileSandbox, FileSandboxConfig

class Sandbox(FileSandbox):
    """Extended sandbox with llm-do specific features."""

    def __init__(self, config: SandboxConfig):
        # SandboxConfig extends FileSandboxConfig with network, etc.
        super().__init__(config)
        self.network_enabled = config.network

# llm_do/approval.py - llm-do specific
class ApprovalController:
    """Approval enforcement for tool calls."""
    ...

# llm_do/os_sandbox.py - llm-do specific
def create_os_sandbox(config: SandboxConfig):
    """OS-level sandbox for shell commands."""
    ...

# llm_do/shell.py - llm-do specific
def shell(command: str, sandbox: Sandbox) -> ShellResult:
    """Execute shell command with OS sandbox and pattern rules."""
    ...
```

---

## Migration Path

### Phase 1: Extract Reusable Core

1. Create `pydantic_ai_contrib_file_sandbox/` package (or similar)
2. Move core classes:
   - `FileSandbox` protocol
   - `FileSandboxConfig`
   - Error classes
   - `FileSandbox` implementation
   - `FileSandboxToolset`
3. Publish as separate package or propose to PydanticAI

### Phase 2: Update llm-do to Use Contrib

1. `llm-do` depends on contrib package
2. `Sandbox` extends `FileSandbox`
3. `SandboxConfig` extends `FileSandboxConfig` with `network`, `require_os_sandbox`
4. Keep approvals, OS sandbox, shell tool in llm-do

### Phase 3: Contribute to PydanticAI

1. Open PR to PydanticAI with contrib package
2. Or publish as `pydantic-ai-file-sandbox` on PyPI
3. Document integration patterns

---

## Benefits of Split

| For PydanticAI Users | For llm-do |
|---------------------|------------|
| Reusable file sandbox | Simpler codebase |
| LLM-friendly errors | Focus on worker orchestration |
| Works with any agent | Can update sandbox independently |
| No opinion on approvals | Keeps opinionated features |

---

## Open Questions

1. **Naming:** `FileSandbox` vs `FSSandbox` vs `PathSandbox`?

2. **Contrib vs separate package:** PydanticAI contrib, or standalone PyPI package?

3. **Async support:** Should methods be async or sync?

## Resolved Questions

| Question | Decision |
|----------|----------|
| Toolset approach | Use `AbstractToolset` for FileSandboxToolset |
| Binary files | `read()` handles text only; binary files use attachments |

---

## Next Steps

1. [ ] Discuss with PydanticAI maintainers if interested
2. [ ] Extract core classes to separate module
3. [ ] Write tests for standalone package
4. [ ] Create example showing integration
5. [ ] Either PR to PydanticAI or publish standalone
