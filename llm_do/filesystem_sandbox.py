"""Backwards-compatible re-export of pydantic-ai-filesystem-sandbox.

This module is deprecated. Import directly from pydantic_ai_filesystem_sandbox instead.

The implementation has been extracted to a standalone package:
https://github.com/zby/pydantic-ai-filesystem-sandbox
"""
from pydantic_ai_filesystem_sandbox import (
    DEFAULT_MAX_READ_CHARS,
    FileSandboxConfig,
    FileSandboxError,
    FileSandboxImpl,
    FileTooLargeError,
    PathConfig,
    PathNotInSandboxError,
    PathNotWritableError,
    ReadResult,
    SuffixNotAllowedError,
)

__all__ = [
    "DEFAULT_MAX_READ_CHARS",
    "FileSandboxConfig",
    "FileSandboxError",
    "FileSandboxImpl",
    "FileTooLargeError",
    "PathConfig",
    "PathNotInSandboxError",
    "PathNotWritableError",
    "ReadResult",
    "SuffixNotAllowedError",
]
