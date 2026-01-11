"""Built-in toolset instances available to every registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from .filesystem import FileSystemToolset, ReadOnlyFileSystemToolset
from .shell import ShellToolset

_SHELL_READONLY_RULES = [
    {"pattern": "wc", "approval_required": False},
    {
        "pattern": "find",
        "approval_required": False,
        "approval_required_if_args": ["-exec", "-execdir", "-delete"],
    },
    {"pattern": "grep", "approval_required": False},
    {"pattern": "head", "approval_required": False},
    {"pattern": "tail", "approval_required": False},
    {"pattern": "sort", "approval_required": False},
    {"pattern": "uniq", "approval_required": False},
    {"pattern": "cat", "approval_required": False},
    {"pattern": "ls", "approval_required": False},
    {"pattern": "git log", "approval_required": False},
    {"pattern": "git diff", "approval_required": False},
    {"pattern": "git show", "approval_required": False},
    {"pattern": "git status", "approval_required": False},
]

_SHELL_FILE_OPS_RULES = [
    {"pattern": "ls", "approval_required": False},
    {"pattern": "mv", "approval_required": True},
]


def _filesystem_config(base_path: Path) -> dict[str, Any]:
    return {
        "base_path": str(base_path.resolve()),
        "read_approval": False,
        "write_approval": True,
    }


def build_builtin_toolsets(
    cwd: Path,
    project_root: Path | None,
) -> dict[str, AbstractToolset[Any]]:
    """Return built-in toolsets keyed by their registry names."""
    cwd_path = cwd.resolve()
    project_path = (project_root or cwd_path).resolve()
    return {
        "filesystem_cwd": FileSystemToolset(config=_filesystem_config(cwd_path)),
        "filesystem_cwd_ro": ReadOnlyFileSystemToolset(
            config=_filesystem_config(cwd_path),
        ),
        "filesystem_project": FileSystemToolset(config=_filesystem_config(project_path)),
        "filesystem_project_ro": ReadOnlyFileSystemToolset(
            config=_filesystem_config(project_path),
        ),
        "shell_readonly": ShellToolset(config={"rules": list(_SHELL_READONLY_RULES)}),
        "shell_file_ops": ShellToolset(config={"rules": list(_SHELL_FILE_OPS_RULES)}),
    }
