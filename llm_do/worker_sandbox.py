"""Extended sandbox with llm-do specific features.

This module extends the reusable Sandbox with:
- Attachment validation for worker delegation

The Sandbox class here is the llm-do specific version.
The base Sandbox is from pydantic_ai_filesystem_sandbox.

Note: For kernel-level isolation, run llm-do inside a Docker container
with appropriate bind mounts and network settings.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from pydantic_ai_filesystem_sandbox import (
    SandboxConfig as BaseSandboxConfig,
    Sandbox as BaseSandbox,
    PathConfig,
    # Re-export errors for convenience
    EditError,
    SandboxError,
    FileTooLargeError,
    PathNotInSandboxError,
    PathNotWritableError,
    SuffixNotAllowedError,
)
from .sandbox import AttachmentInput, AttachmentPayload, AttachmentPolicy


# ---------------------------------------------------------------------------
# Extended Configuration
# ---------------------------------------------------------------------------


# SandboxConfig is just an alias - no llm-do specific extensions currently needed
SandboxConfig = BaseSandboxConfig


# ---------------------------------------------------------------------------
# Extended Implementation
# ---------------------------------------------------------------------------


class Sandbox(BaseSandbox):
    """Extended sandbox with llm-do specific features.

    This is the main sandbox class used in llm-do workers.
    Currently just adds attachment validation compatibility.
    """

    @property
    def sandboxes(self) -> Dict[str, Any]:
        """Dictionary of sandbox names (for compatibility with AttachmentValidator).

        Returns a dict-like object that supports 'in' checks for sandbox names.
        """
        return self._paths


# ---------------------------------------------------------------------------
# Attachment Validation
# ---------------------------------------------------------------------------


class AttachmentValidator:
    """Validates attachments for worker delegation using the new Sandbox."""

    def __init__(self, sandbox: Sandbox):
        """Initialize validator with a Sandbox instance.

        Args:
            sandbox: Sandbox instance providing file access boundaries
        """
        self._sandbox = sandbox

    def validate_attachments(
        self,
        attachment_specs: Optional[Sequence[AttachmentInput]],
        policy: AttachmentPolicy,
    ) -> Tuple[List[Path], List[Dict[str, Any]]]:
        """Resolve attachment specs to sandboxed files and enforce policy limits.

        Args:
            attachment_specs: List of attachment specifications (strings or AttachmentPayload)
            policy: Policy defining attachment constraints

        Returns:
            Tuple of (resolved paths, metadata dicts)

        Raises:
            ValueError: Invalid attachment format
            PermissionError: Attachment outside sandbox or not allowed
            FileNotFoundError: Attachment file doesn't exist
            IsADirectoryError: Attachment is a directory
            KeyError: Unknown sandbox name
        """
        if not attachment_specs:
            return ([], [])

        resolved: List[Path] = []
        metadata: List[Dict[str, Any]] = []

        for spec in attachment_specs:
            if isinstance(spec, AttachmentPayload):
                # Pre-resolved attachment with explicit path
                resolved_path = self._assert_attachment_path(spec)
                resolved.append(resolved_path)
                metadata.append(self._infer_attachment_metadata(spec, resolved_path))
                continue

            # Parse and resolve sandbox-relative attachment
            path, info = self._resolve_attachment(spec)
            resolved.append(path)
            metadata.append(info)

        # Validate against policy constraints
        policy.validate_paths(resolved)
        return (resolved, metadata)

    def _assert_attachment_path(self, payload: AttachmentPayload) -> Path:
        """Validate a pre-resolved AttachmentPayload."""
        path = payload.path.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {payload.display_name}")
        if not path.is_file():
            raise IsADirectoryError(f"Attachment must be a file: {payload.display_name}")
        return path

    def _infer_attachment_metadata(
        self,
        payload: AttachmentPayload,
        resolved_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Infer metadata for a pre-resolved attachment."""
        path = resolved_path or payload.path.expanduser().resolve()
        size = path.stat().st_size

        # Try to identify which sandbox contains this path
        sandbox_name = "external"
        relative = payload.display_name

        for name in self._sandbox.sandboxes:
            try:
                # Get the root path for this sandbox
                sandbox_path = self._sandbox.resolve(f"{name}/.").parent
                rel_path = path.relative_to(sandbox_path)
                sandbox_name = name
                relative = rel_path.as_posix()
                break
            except (ValueError, SandboxError):
                continue

        return {"sandbox": sandbox_name, "path": relative, "bytes": size}

    def _resolve_attachment(
        self,
        spec: Union[str, Path]
    ) -> Tuple[Path, Dict[str, Any]]:
        """Resolve sandbox-relative attachment specification.

        Supports formats:
        - "sandbox_name/relative/path"
        - "sandbox_name:relative/path" (converts to slash format)

        Args:
            spec: Attachment specification string

        Returns:
            Tuple of (resolved path, metadata dict)
        """
        value = str(spec).strip()
        if not value:
            raise ValueError("Attachment path cannot be empty")

        # Normalize path separators
        normalized = value.replace("\\", "/")

        # Reject absolute paths
        if normalized.startswith("/") or normalized.startswith("~"):
            raise PermissionError("Attachments must reference a sandbox, not an absolute path")

        # Support "sandbox:path" format by converting to "sandbox/path"
        if ":" in normalized:
            prefix, suffix = normalized.split(":", 1)
            if prefix in self._sandbox.sandboxes:
                normalized = f"{prefix}/{suffix.lstrip('/')}"

        # Parse path parts
        path = PurePosixPath(normalized)
        parts = path.parts
        if not parts:
            raise ValueError("Attachment path must include a sandbox and file name")

        sandbox_name = parts[0]
        if sandbox_name in {".", ".."}:
            raise PermissionError("Attachments must reference a sandbox name")

        if sandbox_name not in self._sandbox.sandboxes:
            raise KeyError(f"Unknown sandbox '{sandbox_name}' for attachment '{value}'")

        relative_parts = parts[1:]
        if not relative_parts:
            raise ValueError("Attachment path must include a file inside the sandbox")

        # Build full sandbox path and resolve it
        full_path = "/".join(parts)  # "sandbox_name/relative/path"

        try:
            target = self._sandbox.resolve(full_path)
        except SandboxError as e:
            raise PermissionError(f"Cannot access attachment '{value}': {e}")

        # Verify it's a readable file
        if not target.exists():
            raise FileNotFoundError(f"Attachment not found: {value}")
        if not target.is_file():
            raise IsADirectoryError(f"Attachment must be a file: {value}")

        # Build metadata
        size = target.stat().st_size
        relative_path = PurePosixPath(*relative_parts).as_posix()
        info = {"sandbox": sandbox_name, "path": relative_path, "bytes": size}

        return (target, info)



# Re-export for convenience
__all__ = [
    "AttachmentValidator",
    "EditError",
    "SandboxError",
    "FileTooLargeError",
    "PathConfig",
    "PathNotInSandboxError",
    "PathNotWritableError",
    "Sandbox",
    "SandboxConfig",
    "SuffixNotAllowedError",
]
