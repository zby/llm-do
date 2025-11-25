"""Extended sandbox with llm-do specific features.

This module extends the reusable FileSandbox with:
- Network control configuration
- OS sandbox requirement flag
- Future: OS-level enforcement integration

The Sandbox class here is the llm-do specific version.
The base FileSandboxImpl is in file_sandbox.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field

from .file_sandbox import (
    FileSandboxConfig,
    FileSandboxImpl,
    PathConfig,
    # Re-export errors for convenience
    FileSandboxError,
    FileTooLargeError,
    PathNotInSandboxError,
    PathNotWritableError,
    SuffixNotAllowedError,
)


# ---------------------------------------------------------------------------
# Extended Configuration
# ---------------------------------------------------------------------------


class SandboxConfig(FileSandboxConfig):
    """Extended configuration for llm-do sandbox.

    Adds llm-do specific options on top of FileSandboxConfig.
    """

    network: bool = Field(
        default=False,
        description="Whether network access is allowed for shell commands",
    )
    require_os_sandbox: bool = Field(
        default=False,
        description="If True, fail when OS sandbox (Seatbelt/bwrap) is unavailable",
    )


# ---------------------------------------------------------------------------
# Extended Implementation
# ---------------------------------------------------------------------------


class Sandbox(FileSandboxImpl):
    """Extended sandbox with llm-do specific features.

    This is the main sandbox class used in llm-do workers.
    It extends FileSandboxImpl with network control and OS sandbox options.
    """

    def __init__(
        self,
        config: SandboxConfig,
        base_path: Optional[Path] = None,
    ):
        """Initialize the sandbox.

        Args:
            config: Extended sandbox configuration
            base_path: Base path for resolving relative roots (defaults to cwd)
        """
        super().__init__(config, base_path)
        self._extended_config = config

    @property
    def network_enabled(self) -> bool:
        """Whether network access is allowed for shell commands."""
        return self._extended_config.network

    @property
    def require_os_sandbox(self) -> bool:
        """Whether to fail when OS sandbox is unavailable."""
        return self._extended_config.require_os_sandbox


# ---------------------------------------------------------------------------
# Adapter for legacy SandboxConfig
# ---------------------------------------------------------------------------


def sandbox_config_from_legacy(
    sandboxes: dict,
    base_path: Optional[Path] = None,
) -> SandboxConfig:
    """Convert legacy sandboxes dict to new SandboxConfig.

    This enables backward compatibility with existing worker definitions
    that use the old format:

        sandboxes:
          portfolio:
            path: ./portfolio
            mode: rw
            text_suffixes: [.md, .txt]

    Converts to new format:

        sandbox:
          paths:
            portfolio:
              root: ./portfolio
              mode: rw
              suffixes: [.md, .txt]

    Args:
        sandboxes: Legacy sandboxes configuration dict
        base_path: Base path for resolving relative paths

    Returns:
        New-style SandboxConfig
    """
    paths = {}

    for name, cfg in sandboxes.items():
        # Handle both dict and Pydantic model
        if hasattr(cfg, "model_dump"):
            cfg_dict = cfg.model_dump()
        elif hasattr(cfg, "dict"):
            cfg_dict = cfg.dict()
        else:
            cfg_dict = dict(cfg)

        # Map old field names to new ones
        root = cfg_dict.get("path", cfg_dict.get("root", "."))
        mode = cfg_dict.get("mode", "ro")

        # Merge suffix fields - old format had multiple suffix fields
        suffixes = None
        text_suffixes = cfg_dict.get("text_suffixes", [])
        allowed_suffixes = cfg_dict.get("allowed_suffixes", [])
        if text_suffixes or allowed_suffixes:
            suffixes = list(set(text_suffixes + allowed_suffixes))

        max_bytes = cfg_dict.get("max_bytes", cfg_dict.get("max_file_bytes"))

        paths[name] = PathConfig(
            root=str(root),
            mode=mode,
            suffixes=suffixes,
            max_file_bytes=max_bytes,
        )

    return SandboxConfig(paths=paths)


# Re-export for convenience
__all__ = [
    "FileSandboxError",
    "FileTooLargeError",
    "PathConfig",
    "PathNotInSandboxError",
    "PathNotWritableError",
    "Sandbox",
    "SandboxConfig",
    "SuffixNotAllowedError",
    "sandbox_config_from_legacy",
]
