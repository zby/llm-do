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


class AgentApprovalOverride(BaseModel):
    """Per-agent approval override configuration."""

    model_config = ConfigDict(extra="forbid")

    calls_require_approval: bool | None = None
    attachments_require_approval: bool | None = None


# Backwards compatibility alias (deprecated)
WorkerApprovalOverride = AgentApprovalOverride


class ManifestRuntimeConfig(BaseModel):
    """Runtime configuration from manifest."""

    model_config = ConfigDict(extra="forbid")

    approval_mode: ApprovalMode = "prompt"
    max_depth: int = Field(default=5, ge=1)
    return_permission_errors: bool = False
    agent_calls_require_approval: bool = False
    agent_attachments_require_approval: bool = False
    agent_approval_overrides: dict[str, AgentApprovalOverride] = Field(default_factory=dict)
    # Backwards compatibility aliases (deprecated)
    worker_calls_require_approval: bool | None = None
    worker_attachments_require_approval: bool | None = None
    worker_approval_overrides: dict[str, AgentApprovalOverride] | None = None

    @model_validator(mode="after")
    def migrate_worker_fields(self) -> "ManifestRuntimeConfig":
        """Migrate deprecated worker_* fields to agent_* fields."""
        if self.worker_calls_require_approval is not None:
            object.__setattr__(self, "agent_calls_require_approval", self.worker_calls_require_approval)
        if self.worker_attachments_require_approval is not None:
            object.__setattr__(self, "agent_attachments_require_approval", self.worker_attachments_require_approval)
        if self.worker_approval_overrides is not None:
            object.__setattr__(self, "agent_approval_overrides", self.worker_approval_overrides)
        return self


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
    agent_files: list[str] = Field(default_factory=list)
    python_files: list[str] = Field(default_factory=list)
    # Backwards compatibility alias (deprecated)
    worker_files: list[str] | None = None

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        if v != 1:
            raise ValueError(f"Unsupported manifest version: {v}. Only version 1 is supported.")
        return v

    @field_validator("agent_files", "python_files")
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
        # Migrate deprecated worker_files to agent_files
        if self.worker_files is not None:
            object.__setattr__(self, "agent_files", self.worker_files)
        if not self.agent_files and not self.python_files:
            raise ValueError("At least one agent_files or python_files entry is required")
        return self


def load_manifest(manifest_path: str | Path) -> tuple[ProjectManifest, Path]:
    """Load and validate a project manifest from a JSON file or directory.

    Args:
        manifest_path: Path to the manifest JSON file or directory containing project.json

    Returns:
        Tuple of (validated manifest, manifest directory path)

    Raises:
        FileNotFoundError: If manifest file does not exist
        ValueError: If manifest is invalid
    """
    path = Path(manifest_path).resolve()
    if path.is_dir():
        path = path / "project.json"
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
        Tuple of (resolved agent file paths, resolved python file paths)

    Raises:
        FileNotFoundError: If any referenced file does not exist
    """
    agent_paths: list[Path] = []
    python_paths: list[Path] = []

    for agent_file in manifest.agent_files:
        resolved = (manifest_dir / agent_file).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Agent file not found: {agent_file} (resolved: {resolved})")
        agent_paths.append(resolved)

    for python_file in manifest.python_files:
        resolved = (manifest_dir / python_file).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Python file not found: {python_file} (resolved: {resolved})")
        python_paths.append(resolved)

    return agent_paths, python_paths
