"""File sandbox implementation with LLM-friendly errors.

This module provides the reusable core of the sandbox functionality:
- FileSandboxConfig and PathConfig for configuration
- FileSandboxError classes with LLM-friendly messages
- FileSandboxImpl implementation of the FileSandbox protocol

This is designed to be potentially extractable as a PydanticAI contrib package.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class PathConfig(BaseModel):
    """Configuration for a single path in the sandbox."""

    root: str = Field(description="Root directory path")
    mode: Literal["ro", "rw"] = Field(
        default="ro", description="Access mode: 'ro' (read-only) or 'rw' (read-write)"
    )
    suffixes: Optional[list[str]] = Field(
        default=None,
        description="Allowed file suffixes (e.g., ['.md', '.txt']). None means all allowed.",
    )
    max_file_bytes: Optional[int] = Field(
        default=None, description="Maximum file size in bytes. None means no limit."
    )


class FileSandboxConfig(BaseModel):
    """Configuration for a file sandbox."""

    paths: dict[str, PathConfig] = Field(
        default_factory=dict,
        description="Named paths with their configurations",
    )


# ---------------------------------------------------------------------------
# LLM-Friendly Errors
# ---------------------------------------------------------------------------


class FileSandboxError(Exception):
    """Base class for sandbox errors with LLM-friendly messages.

    All sandbox errors include guidance on what IS allowed,
    helping the LLM correct its behavior.
    """

    pass


class PathNotInSandboxError(FileSandboxError):
    """Raised when a path is outside all sandbox boundaries."""

    def __init__(self, path: str, readable_roots: list[str]):
        self.path = path
        self.readable_roots = readable_roots
        roots_str = ", ".join(readable_roots) if readable_roots else "none"
        self.message = (
            f"Cannot access '{path}': path is outside sandbox.\n"
            f"Readable paths: {roots_str}"
        )
        super().__init__(self.message)


class PathNotWritableError(FileSandboxError):
    """Raised when trying to write to a read-only path."""

    def __init__(self, path: str, writable_roots: list[str]):
        self.path = path
        self.writable_roots = writable_roots
        roots_str = ", ".join(writable_roots) if writable_roots else "none"
        self.message = (
            f"Cannot write to '{path}': path is read-only.\n"
            f"Writable paths: {roots_str}"
        )
        super().__init__(self.message)


class SuffixNotAllowedError(FileSandboxError):
    """Raised when file suffix is not in the allowed list."""

    def __init__(self, path: str, suffix: str, allowed: list[str]):
        self.path = path
        self.suffix = suffix
        self.allowed = allowed
        allowed_str = ", ".join(allowed) if allowed else "any"
        self.message = (
            f"Cannot access '{path}': suffix '{suffix}' not allowed.\n"
            f"Allowed suffixes: {allowed_str}"
        )
        super().__init__(self.message)


class FileTooLargeError(FileSandboxError):
    """Raised when file exceeds size limit."""

    def __init__(self, path: str, size: int, limit: int):
        self.path = path
        self.size = size
        self.limit = limit
        self.message = (
            f"Cannot read '{path}': file too large ({size:,} bytes).\n"
            f"Maximum allowed: {limit:,} bytes"
        )
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


class FileSandboxImpl:
    """File sandbox implementation with LLM-friendly error messages.

    Implements the FileSandbox protocol defined in protocols.py.
    """

    def __init__(self, config: FileSandboxConfig, base_path: Optional[Path] = None):
        """Initialize the file sandbox.

        Args:
            config: Sandbox configuration
            base_path: Base path for resolving relative roots (defaults to cwd)
        """
        self.config = config
        self._base_path = base_path or Path.cwd()
        self._paths: dict[str, tuple[Path, PathConfig]] = {}
        self._setup_paths()

    def _setup_paths(self) -> None:
        """Resolve and validate configured paths."""
        for name, path_config in self.config.paths.items():
            root = Path(path_config.root)
            if not root.is_absolute():
                root = (self._base_path / root).resolve()
            else:
                root = root.resolve()
            # Create directory if it doesn't exist
            root.mkdir(parents=True, exist_ok=True)
            self._paths[name] = (root, path_config)

    @property
    def readable_roots(self) -> list[str]:
        """List of readable path roots (for error messages)."""
        return [name for name in self._paths.keys()]

    @property
    def writable_roots(self) -> list[str]:
        """List of writable path roots (for error messages)."""
        return [
            name
            for name, (_, config) in self._paths.items()
            if config.mode == "rw"
        ]

    def _find_path_for(self, path: str) -> tuple[str, Path, PathConfig]:
        """Find which sandbox path contains the given path.

        Args:
            path: Path to look up (can be "sandbox_name/relative" or absolute)

        Returns:
            Tuple of (sandbox_name, resolved_path, path_config)

        Raises:
            PathNotInSandboxError: If path is not in any sandbox
        """
        # Handle "sandbox_name/relative/path" format
        if "/" in path and not path.startswith("/"):
            parts = path.split("/", 1)
            sandbox_name = parts[0]
            if sandbox_name in self._paths:
                root, config = self._paths[sandbox_name]
                relative = parts[1] if len(parts) > 1 else ""
                resolved = self._resolve_within(root, relative)
                return (sandbox_name, resolved, config)

        # Handle "sandbox_name:relative/path" format
        if ":" in path:
            parts = path.split(":", 1)
            sandbox_name = parts[0]
            if sandbox_name in self._paths:
                root, config = self._paths[sandbox_name]
                relative = parts[1].lstrip("/") if len(parts) > 1 else ""
                resolved = self._resolve_within(root, relative)
                return (sandbox_name, resolved, config)

        # Try to find path in any sandbox
        check_path = Path(path)
        if check_path.is_absolute():
            check_path = check_path.resolve()
            for name, (root, config) in self._paths.items():
                try:
                    check_path.relative_to(root)
                    return (name, check_path, config)
                except ValueError:
                    continue

        raise PathNotInSandboxError(path, self.readable_roots)

    def _resolve_within(self, root: Path, relative: str) -> Path:
        """Resolve a relative path within a root, preventing escapes.

        Args:
            root: The sandbox root directory
            relative: Relative path within the sandbox

        Returns:
            Resolved absolute path

        Raises:
            PathNotInSandboxError: If resolved path escapes the root
        """
        relative = relative.lstrip("/")
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise PathNotInSandboxError(
                relative, self.readable_roots
            )
        return candidate

    def can_read(self, path: str) -> bool:
        """Check if path is readable within sandbox boundaries."""
        try:
            self._find_path_for(path)
            return True
        except FileSandboxError:
            return False

    def can_write(self, path: str) -> bool:
        """Check if path is writable within sandbox boundaries."""
        try:
            _, _, config = self._find_path_for(path)
            return config.mode == "rw"
        except FileSandboxError:
            return False

    def resolve(self, path: str) -> Path:
        """Resolve path within sandbox.

        Args:
            path: Relative or absolute path to resolve

        Returns:
            Resolved absolute Path

        Raises:
            PathNotInSandboxError: If path is outside sandbox boundaries
        """
        _, resolved, _ = self._find_path_for(path)
        return resolved

    def _check_suffix(self, path: Path, config: PathConfig) -> None:
        """Check if file suffix is allowed.

        Raises:
            SuffixNotAllowedError: If suffix is not in allowed list
        """
        if config.suffixes is not None:
            suffix = path.suffix.lower()
            allowed = [s.lower() for s in config.suffixes]
            if suffix not in allowed:
                raise SuffixNotAllowedError(str(path), suffix, config.suffixes)

    def _check_size(self, path: Path, config: PathConfig) -> None:
        """Check if file size is within limit.

        Raises:
            FileTooLargeError: If file exceeds size limit
        """
        if config.max_file_bytes is not None and path.exists():
            size = path.stat().st_size
            if size > config.max_file_bytes:
                raise FileTooLargeError(str(path), size, config.max_file_bytes)

    def read(self, path: str, max_chars: int = 200_000) -> str:
        """Read text file from sandbox.

        Args:
            path: Path to file (relative to sandbox)
            max_chars: Maximum characters to read

        Returns:
            File contents as string

        Raises:
            PathNotInSandboxError: If path outside sandbox
            SuffixNotAllowedError: If suffix not allowed
            FileTooLargeError: If file too large
            FileNotFoundError: If file doesn't exist
        """
        name, resolved, config = self._find_path_for(path)

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not resolved.is_file():
            raise IsADirectoryError(f"Not a file: {path}")

        self._check_suffix(resolved, config)
        self._check_size(resolved, config)

        text = resolved.read_text(encoding="utf-8")
        if len(text) > max_chars:
            text = text[:max_chars]
            # Could add truncation notice, but keeping simple for now

        return text

    def write(self, path: str, content: str) -> str:
        """Write text file to sandbox.

        Args:
            path: Path to file (relative to sandbox)
            content: Content to write

        Returns:
            Confirmation message

        Raises:
            PathNotInSandboxError: If path outside sandbox
            PathNotWritableError: If path is read-only
            SuffixNotAllowedError: If suffix not allowed
        """
        name, resolved, config = self._find_path_for(path)

        if config.mode != "rw":
            raise PathNotWritableError(path, self.writable_roots)

        self._check_suffix(resolved, config)

        # Check content size against limit
        if config.max_file_bytes is not None:
            content_bytes = len(content.encode("utf-8"))
            if content_bytes > config.max_file_bytes:
                raise FileTooLargeError(path, content_bytes, config.max_file_bytes)

        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)

        resolved.write_text(content, encoding="utf-8")
        return f"Written {len(content)} characters to {name}/{resolved.relative_to(self._paths[name][0])}"

    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files matching pattern within sandbox.

        Args:
            path: Base path to search from (sandbox name or sandbox_name/subdir)
            pattern: Glob pattern to match

        Returns:
            List of matching file paths (as sandbox_name/relative format)
        """
        # If path is "." or empty, list all sandboxes
        if path in (".", ""):
            results = []
            for name, (root, _) in self._paths.items():
                for match in root.glob(pattern):
                    if match.is_file():
                        try:
                            rel = match.relative_to(root)
                            results.append(f"{name}/{rel}")
                        except ValueError:
                            continue
            return sorted(results)

        # Otherwise, find the specific path
        try:
            name, resolved, _ = self._find_path_for(path)
        except PathNotInSandboxError:
            # Path might be just a sandbox name
            if path in self._paths:
                name = path
                resolved, _ = self._paths[name]
            else:
                raise

        root, _ = self._paths[name]
        results = []
        for match in resolved.glob(pattern):
            if match.is_file():
                try:
                    rel = match.relative_to(root)
                    results.append(f"{name}/{rel}")
                except ValueError:
                    continue
        return sorted(results)
