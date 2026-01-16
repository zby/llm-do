"""Project manifest schema and loader.

This module defines the Pydantic models for the manifest-driven CLI.
The manifest is a JSON file that specifies the project configuration,
including runtime settings, entry config, and file references.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ApprovalMode = Literal["prompt", "approve_all", "reject_all"]


class WorkerApprovalOverride(BaseModel):
    """Per-worker approval override configuration."""

    model_config = ConfigDict(extra="forbid")

    calls_require_approval: bool | None = None
    attachments_require_approval: bool | None = None


class ManifestRuntimeConfig(BaseModel):
    """Runtime configuration from manifest."""

    model_config = ConfigDict(extra="forbid")

    approval_mode: ApprovalMode = "prompt"
    max_depth: int = Field(default=5, ge=1)
    return_permission_errors: bool = False
    worker_calls_require_approval: bool = False
    worker_attachments_require_approval: bool = False
    worker_approval_overrides: dict[str, WorkerApprovalOverride] = Field(default_factory=dict)


class EntryConfig(BaseModel):
    """Entry point configuration from manifest."""

    model_config = ConfigDict(extra="forbid")

    input: dict[str, Any] | None = None


class ProjectManifest(BaseModel):
    """Project manifest schema (v1).

    The manifest is the authoritative source for project configuration.
    File paths are resolved relative to the manifest directory.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = Field(...)
    runtime: ManifestRuntimeConfig
    allow_cli_input: bool = True
    entry: EntryConfig
    worker_files: list[str] = Field(default_factory=list)
    python_files: list[str] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        if v != 1:
            raise ValueError(f"Unsupported manifest version: {v}. Only version 1 is supported.")
        return v

    @field_validator("worker_files", "python_files")
    @classmethod
    def validate_file_list(cls, v: list[str]) -> list[str]:
        # Check for empty strings
        for path in v:
            if not path or not path.strip():
                raise ValueError("File paths must be non-empty strings")
        # Check for duplicates
        if len(v) != len(set(v)):
            seen = set()
            duplicates = []
            for path in v:
                if path in seen:
                    duplicates.append(path)
                seen.add(path)
            raise ValueError(f"Duplicate file paths: {duplicates}")
        return v

    @model_validator(mode="after")
    def validate_has_files(self) -> "ProjectManifest":
        if not self.worker_files and not self.python_files:
            raise ValueError("At least one worker_files or python_files entry is required")
        return self


def load_manifest(manifest_path: str | Path) -> tuple[ProjectManifest, Path]:
    """Load and validate a project manifest from a JSON file.

    Args:
        manifest_path: Path to the manifest JSON file

    Returns:
        Tuple of (validated manifest, manifest directory path)

    Raises:
        FileNotFoundError: If manifest file does not exist
        ValueError: If manifest is invalid
    """
    path = Path(manifest_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in manifest file: {e}") from e

    try:
        manifest = ProjectManifest.model_validate(data)
    except Exception as e:
        raise ValueError(f"Invalid manifest: {e}") from e

    return manifest, path.parent


def resolve_manifest_paths(
    manifest: ProjectManifest,
    manifest_dir: Path,
) -> tuple[list[Path], list[Path]]:
    """Resolve file paths relative to the manifest directory.

    Args:
        manifest: The validated manifest
        manifest_dir: Directory containing the manifest file

    Returns:
        Tuple of (resolved worker file paths, resolved python file paths)

    Raises:
        FileNotFoundError: If any referenced file does not exist
    """
    worker_paths: list[Path] = []
    python_paths: list[Path] = []

    for worker_file in manifest.worker_files:
        resolved = (manifest_dir / worker_file).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Worker file not found: {worker_file} (resolved: {resolved})")
        worker_paths.append(resolved)

    for python_file in manifest.python_files:
        resolved = (manifest_dir / python_file).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Python file not found: {python_file} (resolved: {resolved})")
        python_paths.append(resolved)

    return worker_paths, python_paths
