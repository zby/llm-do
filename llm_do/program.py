"""Program detection and configuration loading for llm-do.

This module handles the worker-as-function architecture where programs
are directories with a main.worker entry point and optional program.yaml
configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import yaml
from pydantic import ValidationError

from .types import InvocationMode, ProgramConfig


class InvalidProgramError(Exception):
    """Raised when a directory doesn't have a valid program structure."""
    pass


@dataclass
class ProgramContext:
    """Resolved program context for worker execution.

    This contains all the information needed to run a worker within a program,
    including the program root, configuration, and entry point.
    """

    program_root: Path
    config: ProgramConfig
    entry_worker: str  # Worker name to run (default: "main")


def detect_invocation_mode(arg: str) -> InvocationMode:
    """Detect whether argument is program, worker file, or worker name.

    Args:
        arg: CLI argument (path or worker name)

    Returns:
        InvocationMode indicating how to interpret the argument
    """
    path = Path(arg)

    # Explicit .worker file
    if path.is_file() and path.suffix == ".worker":
        return InvocationMode.SINGLE_FILE

    # Directory - check for program markers
    if path.is_dir():
        if (path / "main.worker").exists():
            return InvocationMode.PROGRAM
        if (path / "program.yaml").exists():
            return InvocationMode.PROGRAM
        # Directory exists but no program markers
        raise InvalidProgramError(
            f"Directory '{path}' is not a valid program: missing main.worker"
        )

    # Not a file or directory - treat as worker name for path search
    return InvocationMode.SEARCH_PATH


def load_program_config(program_root: Path) -> ProgramConfig:
    """Load program configuration from program.yaml.

    Args:
        program_root: Path to program directory

    Returns:
        ProgramConfig (empty config if no program.yaml exists)

    Raises:
        ValueError: If program.yaml exists but is invalid
    """
    config_path = program_root / "program.yaml"

    if not config_path.exists():
        # No manifest - return empty config (program still valid with just main.worker)
        return ProgramConfig()

    try:
        content = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or {}
        return ProgramConfig.model_validate(data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
    except ValidationError as e:
        raise ValueError(f"Invalid program configuration in {config_path}: {e}") from e


def resolve_program(
    arg: str,
    *,
    entry_override: Optional[str] = None,
) -> Tuple[InvocationMode, Optional[ProgramContext], str]:
    """Resolve CLI argument to invocation mode, program context, and worker name.

    This is the main entry point for program resolution. It handles:
    - Program directories (with main.worker)
    - Single .worker files
    - Worker names (for LLM_DO_PATH search)

    Args:
        arg: CLI argument (path or worker name)
        entry_override: Optional --entry flag to override entry point

    Returns:
        Tuple of (mode, program_context, worker_name)
        - For PROGRAM mode: (PROGRAM, ProgramContext, entry_worker)
        - For SINGLE_FILE mode: (SINGLE_FILE, None, file_path)
        - For SEARCH_PATH mode: (SEARCH_PATH, None, worker_name)

    Raises:
        InvalidProgramError: If directory exists but isn't a valid program
        ValueError: If program.yaml is invalid
    """
    mode = detect_invocation_mode(arg)

    if mode == InvocationMode.PROGRAM:
        program_root = Path(arg).resolve()
        config = load_program_config(program_root)
        entry_worker = entry_override or "main"

        context = ProgramContext(
            program_root=program_root,
            config=config,
            entry_worker=entry_worker,
        )
        return mode, context, entry_worker

    elif mode == InvocationMode.SINGLE_FILE:
        # Single file - no program context
        file_path = Path(arg).resolve()
        return mode, None, str(file_path)

    else:  # SEARCH_PATH
        # Worker name - search LLM_DO_PATH
        return mode, None, arg
