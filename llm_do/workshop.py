"""Workshop detection and configuration loading for llm-do.

This module handles the worker-as-function architecture where workshops
are directories with a main.worker entry point and optional workshop.yaml
configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import yaml
from pydantic import ValidationError

from .types import InvocationMode, WorkshopConfig


class InvalidWorkshopError(Exception):
    """Raised when a directory doesn't have a valid workshop structure."""
    pass


@dataclass
class WorkshopContext:
    """Resolved workshop context for worker execution.

    This contains all the information needed to run a worker within a workshop,
    including the workshop root, configuration, and entry point.
    """

    workshop_root: Path
    config: WorkshopConfig
    entry_worker: str  # Worker name to run (default: "main")


def detect_invocation_mode(arg: str) -> InvocationMode:
    """Detect whether argument is workshop, worker file, or worker name.

    Args:
        arg: CLI argument (path or worker name)

    Returns:
        InvocationMode indicating how to interpret the argument
    """
    path = Path(arg)

    # Explicit .worker file
    if path.is_file() and path.suffix == ".worker":
        return InvocationMode.SINGLE_FILE

    # Directory - check for workshop markers
    if path.is_dir():
        if (path / "main.worker").exists():
            return InvocationMode.WORKSHOP
        if (path / "workshop.yaml").exists():
            return InvocationMode.WORKSHOP
        # Directory exists but no workshop markers
        raise InvalidWorkshopError(
            f"Directory '{path}' is not a valid workshop: missing main.worker"
        )

    # Not a file or directory - treat as worker name for path search
    return InvocationMode.SEARCH_PATH


def load_workshop_config(workshop_root: Path) -> WorkshopConfig:
    """Load workshop configuration from workshop.yaml.

    Args:
        workshop_root: Path to workshop directory

    Returns:
        WorkshopConfig (empty config if no workshop.yaml exists)

    Raises:
        ValueError: If workshop.yaml exists but is invalid
    """
    config_path = workshop_root / "workshop.yaml"

    if not config_path.exists():
        # No manifest - return empty config (workshop still valid with just main.worker)
        return WorkshopConfig()

    try:
        content = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        return WorkshopConfig.model_validate(data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
    except ValidationError as e:
        raise ValueError(f"Invalid workshop configuration in {config_path}: {e}") from e


def resolve_workshop(
    arg: str,
    *,
    entry_override: Optional[str] = None,
) -> Tuple[InvocationMode, Optional[WorkshopContext], str]:
    """Resolve CLI argument to invocation mode, workshop context, and worker name.

    This is the main entry point for workshop resolution. It handles:
    - Workshop directories (with main.worker)
    - Single .worker files
    - Worker names (for LLM_DO_PATH search)

    Args:
        arg: CLI argument (path or worker name)
        entry_override: Optional --entry flag to override entry point

    Returns:
        Tuple of (mode, workshop_context, worker_name)
        - For WORKSHOP mode: (WORKSHOP, WorkshopContext, entry_worker)
        - For SINGLE_FILE mode: (SINGLE_FILE, None, file_path)
        - For SEARCH_PATH mode: (SEARCH_PATH, None, worker_name)

    Raises:
        InvalidWorkshopError: If directory exists but isn't a valid workshop
        ValueError: If workshop.yaml is invalid
    """
    mode = detect_invocation_mode(arg)

    if mode == InvocationMode.WORKSHOP:
        workshop_root = Path(arg).resolve()
        config = load_workshop_config(workshop_root)
        entry_worker = entry_override or "main"

        context = WorkshopContext(
            workshop_root=workshop_root,
            config=config,
            entry_worker=entry_worker,
        )
        return mode, context, entry_worker

    elif mode == InvocationMode.SINGLE_FILE:
        # Single file - no workshop context
        file_path = Path(arg).resolve()
        return mode, None, str(file_path)

    else:  # SEARCH_PATH
        # Worker name - search LLM_DO_PATH
        return mode, None, arg
