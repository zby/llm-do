"""Worker resolution for llm-do.

This module handles resolving CLI arguments to worker paths or names.
Simple two-mode resolution:
- Explicit path: ./path/to/worker.worker or /absolute/path.worker
- Name search: Look in registry root
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from .types import InvocationMode


def detect_invocation_mode(arg: str) -> InvocationMode:
    """Detect whether argument is a worker file path or a worker name.

    Args:
        arg: CLI argument (path or worker name)

    Returns:
        InvocationMode indicating how to interpret the argument
    """
    path = Path(arg)

    # Explicit .worker file
    if path.is_file() and path.suffix == ".worker":
        return InvocationMode.SINGLE_FILE

    # Explicit path syntax (starts with ./ or / or has .worker suffix)
    if arg.startswith('./') or arg.startswith('/') or path.suffix == ".worker":
        return InvocationMode.SINGLE_FILE

    # Plain worker name - search in registry
    return InvocationMode.SEARCH_PATH


def resolve_worker(arg: str) -> Tuple[InvocationMode, str]:
    """Resolve CLI argument to invocation mode and worker name.

    This is the main entry point for worker resolution. It handles:
    - Single .worker files (explicit paths)
    - Worker names (for registry search)

    Args:
        arg: CLI argument (path or worker name)

    Returns:
        Tuple of (mode, worker_name_or_path)
        - For SINGLE_FILE mode: (SINGLE_FILE, file_path_string)
        - For SEARCH_PATH mode: (SEARCH_PATH, worker_name)
    """
    mode = detect_invocation_mode(arg)

    if mode == InvocationMode.SINGLE_FILE:
        # Resolve to absolute path
        file_path = Path(arg).resolve()
        return mode, str(file_path)

    # SEARCH_PATH - worker name
    return mode, arg
