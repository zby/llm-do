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
AuthMode = Literal["oauth_off", "oauth_auto", "oauth_required"]


class AgentApprovalOverride(BaseModel):
    """Per-agent approval override configuration."""

    model_config = ConfigDict(extra="forbid")

    calls_require_approval: bool | None = None
    attachments_require_approval: bool | None = None


class ManifestRuntimeConfig(BaseModel):
    """Runtime configuration from manifest."""

    model_config = ConfigDict(extra="forbid")

    approval_mode: ApprovalMode = "prompt"
    auth_mode: AuthMode = "oauth_off"
    max_depth: int = Field(default=5, ge=1)
    return_permission_errors: bool = False
    agent_calls_require_approval: bool = False
    agent_attachments_require_approval: bool = False
    agent_approval_overrides: dict[str, AgentApprovalOverride] = Field(default_factory=dict)


class EntryConfig(BaseModel):
    """Entry point configuration from manifest."""

    model_config = ConfigDict(extra="forbid")

    agent: str | None = None
    function: str | None = None
    args: dict[str, Any] | None = None

    @field_validator("agent", "function")
    @classmethod
    def validate_entry_target(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str) or not v.strip():
            raise ValueError("entry target must be a non-empty string")
        return v

    @model_validator(mode="after")
    def validate_entry_target_set(self) -> "EntryConfig":
        if bool(self.agent) == bool(self.function):
            raise ValueError("entry must define exactly one of 'agent' or 'function'")
        return self


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
    generated_agents_dir: str | None = None
    agent_files: list[str] = Field(default_factory=list)
    python_files: list[str] = Field(default_factory=list)

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

    @field_validator("generated_agents_dir")
    @classmethod
    def validate_generated_agents_dir(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("generated_agents_dir must be a non-empty string")
        return v

    @model_validator(mode="after")
    def validate_has_files(self) -> "ProjectManifest":
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


def resolve_generated_agents_dir(
    manifest: ProjectManifest,
    manifest_dir: Path,
) -> Path | None:
    """Resolve generated_agents_dir relative to the manifest directory."""
    if manifest.generated_agents_dir is None:
        return None
    path = Path(manifest.generated_agents_dir).expanduser()
    if not path.is_absolute():
        return (manifest_dir / path).resolve()
    return path.resolve()
