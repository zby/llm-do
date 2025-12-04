"""Project detection and configuration loading for llm-do.

This module handles the worker-as-function architecture where projects
are directories with a main.worker entry point and optional project.yaml
configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import yaml
from pydantic import ValidationError

from .types import InvocationMode, ProjectConfig


class InvalidProjectError(Exception):
    """Raised when a directory doesn't have a valid project structure."""
    pass


@dataclass
class ProjectContext:
    """Resolved project context for worker execution.

    This contains all the information needed to run a worker within a project,
    including the project root, configuration, and entry point.
    """

    project_root: Path
    config: ProjectConfig
    entry_worker: str  # Worker name to run (default: "main")

    @property
    def workers_dir(self) -> Path:
        """Path to project's workers directory."""
        return self.project_root / "workers"

    @property
    def templates_dir(self) -> Path:
        """Path to project's templates directory."""
        return self.project_root / "templates"

    @property
    def tools_path(self) -> Optional[Path]:
        """Path to project's tools.py if it exists."""
        simple = self.project_root / "tools.py"
        if simple.exists():
            return simple
        package = self.project_root / "tools" / "__init__.py"
        if package.exists():
            return package.parent
        return None


def detect_invocation_mode(arg: str) -> InvocationMode:
    """Detect whether argument is project, worker file, or worker name.

    Args:
        arg: CLI argument (path or worker name)

    Returns:
        InvocationMode indicating how to interpret the argument
    """
    path = Path(arg)

    # Explicit .worker file
    if path.is_file() and path.suffix == ".worker":
        return InvocationMode.SINGLE_FILE

    # Directory - check for project markers
    if path.is_dir():
        if (path / "main.worker").exists():
            return InvocationMode.PROJECT
        if (path / "project.yaml").exists():
            return InvocationMode.PROJECT
        # Directory exists but no project markers
        raise InvalidProjectError(
            f"Directory '{path}' is not a valid project: missing main.worker"
        )

    # Not a file or directory - treat as worker name for path search
    return InvocationMode.SEARCH_PATH


def load_project_config(project_root: Path) -> ProjectConfig:
    """Load project configuration from project.yaml.

    Args:
        project_root: Path to project directory

    Returns:
        ProjectConfig (empty config if no project.yaml exists)

    Raises:
        ValueError: If project.yaml exists but is invalid
    """
    config_path = project_root / "project.yaml"

    if not config_path.exists():
        # No manifest - return empty config (project still valid with just main.worker)
        return ProjectConfig()

    try:
        content = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        return ProjectConfig.model_validate(data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
    except ValidationError as e:
        raise ValueError(f"Invalid project configuration in {config_path}: {e}") from e


def resolve_project(
    arg: str,
    *,
    entry_override: Optional[str] = None,
) -> Tuple[InvocationMode, Optional[ProjectContext], str]:
    """Resolve CLI argument to invocation mode, project context, and worker name.

    This is the main entry point for project resolution. It handles:
    - Project directories (with main.worker)
    - Single .worker files
    - Worker names (for LLM_DO_PATH search)

    Args:
        arg: CLI argument (path or worker name)
        entry_override: Optional --entry flag to override entry point

    Returns:
        Tuple of (mode, project_context, worker_name)
        - For PROJECT mode: (PROJECT, ProjectContext, entry_worker)
        - For SINGLE_FILE mode: (SINGLE_FILE, None, file_path)
        - For SEARCH_PATH mode: (SEARCH_PATH, None, worker_name)

    Raises:
        InvalidProjectError: If directory exists but isn't a valid project
        ValueError: If project.yaml is invalid
    """
    mode = detect_invocation_mode(arg)

    if mode == InvocationMode.PROJECT:
        project_root = Path(arg).resolve()
        config = load_project_config(project_root)
        entry_worker = entry_override or "main"

        context = ProjectContext(
            project_root=project_root,
            config=config,
            entry_worker=entry_worker,
        )
        return mode, context, entry_worker

    elif mode == InvocationMode.SINGLE_FILE:
        # Single file - no project context
        file_path = Path(arg).resolve()
        return mode, None, str(file_path)

    else:  # SEARCH_PATH
        # Worker name - search LLM_DO_PATH
        return mode, None, arg


def find_entry_worker_path(project_root: Path, entry_name: str = "main") -> Path:
    """Find the entry worker file in a project.

    Searches for the worker in order:
    1. {project_root}/main.worker (if entry_name == "main")
    2. {project_root}/workers/{entry_name}.worker
    3. {project_root}/workers/{entry_name}/worker.worker

    Args:
        project_root: Path to project directory
        entry_name: Name of entry worker (default: "main")

    Returns:
        Path to the worker file

    Raises:
        FileNotFoundError: If entry worker not found
    """
    candidates = []

    # Special case: main.worker at project root
    if entry_name == "main":
        root_main = project_root / "main.worker"
        candidates.append(root_main)

    # Standard locations in workers/
    candidates.extend([
        project_root / "workers" / f"{entry_name}.worker",
        project_root / "workers" / entry_name / "worker.worker",
    ])

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Entry worker '{entry_name}' not found in project. "
        f"Searched: {', '.join(str(p) for p in candidates)}"
    )
