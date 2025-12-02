"""Protocol definitions for dependency injection.

These protocols define the interfaces that tools and other components
depend on, without coupling to concrete runtime implementations.

This enables clean separation between tool registration (tools.py) and
runtime orchestration (runtime.py) without circular dependencies.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

from pydantic_ai_filesystem_sandbox import DEFAULT_MAX_READ_CHARS

if TYPE_CHECKING:
    from pydantic_ai_filesystem_sandbox import ReadResult


# ---------------------------------------------------------------------------
# FileSandbox Protocol (reusable core - potential PydanticAI contrib)
# ---------------------------------------------------------------------------


class FileSandbox(Protocol):
    """Protocol for sandboxed file operations with LLM-friendly errors.

    This is the reusable core that could be contributed to PydanticAI.
    Tools depend on this protocol, not concrete implementations.

    All error messages should guide the LLM to correct behavior by
    including what IS allowed, not just what failed.
    """

    def can_read(self, path: str) -> bool:
        """Check if path is readable within sandbox boundaries."""
        ...

    def can_write(self, path: str) -> bool:
        """Check if path is writable within sandbox boundaries."""
        ...

    def resolve(self, path: str) -> Path:
        """Resolve path within sandbox.

        Args:
            path: Relative or absolute path to resolve

        Returns:
            Resolved absolute Path

        Raises:
            SandboxError: If path is outside sandbox boundaries
        """
        ...

    def read(self, path: str, max_chars: int = DEFAULT_MAX_READ_CHARS, offset: int = 0) -> ReadResult:
        """Read text file from sandbox.

        Args:
            path: Path to file (relative to sandbox)
            max_chars: Maximum characters to read (default: DEFAULT_MAX_READ_CHARS)
            offset: Character position to start reading from (default: 0)

        Returns:
            ReadResult with content, truncation info, and metadata

        Raises:
            SandboxError: If path outside sandbox, suffix not allowed, etc.
            FileNotFoundError: If file doesn't exist
        """
        ...

    def write(self, path: str, content: str) -> str:
        """Write text file to sandbox.

        Args:
            path: Path to file (relative to sandbox)
            content: Content to write

        Returns:
            Confirmation message

        Raises:
            SandboxError: If path outside sandbox, not writable, etc.
        """
        ...

    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files matching pattern within sandbox.

        Args:
            path: Base path to search from
            pattern: Glob pattern to match

        Returns:
            List of matching file paths (relative to sandbox)
        """
        ...

    @property
    def readable_roots(self) -> list[str]:
        """List of readable path roots (for error messages)."""
        ...

    @property
    def writable_roots(self) -> list[str]:
        """List of writable path roots (for error messages)."""
        ...


# ---------------------------------------------------------------------------
# Worker Protocols
# ---------------------------------------------------------------------------


class WorkerDelegator(Protocol):
    """Protocol for delegating to other workers.

    Concrete implementation lives in runtime.py to avoid circular imports.
    Tools depend on this protocol rather than importing call_worker directly.
    """

    async def call_async(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Delegate to another worker asynchronously.

        Args:
            worker: Name of the worker to delegate to
            input_data: Input payload for the worker
            attachments: Optional list of attachment paths (sandbox-relative)

        Returns:
            Output from the delegated worker

        Raises:
            PermissionError: If delegation is not allowed or user rejects
        """
        ...

    def call_sync(
        self,
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        """Delegate to another worker synchronously.

        Args:
            worker: Name of the worker to delegate to
            input_data: Input payload for the worker
            attachments: Optional list of attachment paths (sandbox-relative)

        Returns:
            Output from the delegated worker

        Raises:
            PermissionError: If delegation is not allowed or user rejects
        """
        ...


class WorkerCreator(Protocol):
    """Protocol for creating new workers.

    Concrete implementation lives in runtime.py.
    Tools depend on this protocol for the worker_create tool.
    """

    def create(
        self,
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Create and persist a new worker definition.

        Args:
            name: Worker name (used for file path and identification)
            instructions: System prompt for the worker
            description: Optional human-readable description
            model: Optional model override (defaults to profile default)
            output_schema_ref: Optional reference to output schema
            force: If True, overwrite existing worker definition

        Returns:
            Dictionary representation of the created WorkerDefinition

        Raises:
            PermissionError: If creation is not allowed or user rejects
            FileExistsError: If worker exists and force=False
        """
        ...
