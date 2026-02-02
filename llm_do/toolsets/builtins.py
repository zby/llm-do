"""Built-in toolset instances available to every registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets._dynamic import DynamicToolset

from .dynamic_agents import DynamicAgentsToolset
from .filesystem import FileSystemToolset, ReadOnlyFileSystemToolset
from .loader import ToolsetDef
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


def _per_run_toolset(factory: Callable[[], AbstractToolset[Any]]) -> ToolsetDef:
    def build(_ctx: RunContext[Any]) -> AbstractToolset[Any]:
        return factory()

    return DynamicToolset(toolset_func=build, per_run_step=False)


def build_builtin_toolsets(
    cwd: Path,
    project_root: Path | None,
) -> dict[str, ToolsetDef]:
    """Return built-in toolset defs keyed by their registry names."""
    cwd_path = cwd.resolve()
    project_path = (project_root or cwd_path).resolve()
    cwd_config = _filesystem_config(cwd_path)
    project_config = _filesystem_config(project_path)

    def filesystem_factory(
        config: dict[str, Any],
        *,
        read_only: bool,
    ) -> ToolsetDef:
        def factory() -> AbstractToolset[Any]:
            if read_only:
                return ReadOnlyFileSystemToolset(config=dict(config))
            return FileSystemToolset(config=dict(config))

        return _per_run_toolset(factory)

    def shell_factory(rules: list[dict[str, Any]]) -> ToolsetDef:
        def factory() -> AbstractToolset[Any]:
            return ShellToolset(config={"rules": [dict(rule) for rule in rules]})

        return _per_run_toolset(factory)

    return {
        "filesystem_cwd": filesystem_factory(cwd_config, read_only=False),
        "filesystem_cwd_ro": filesystem_factory(cwd_config, read_only=True),
        "filesystem_project": filesystem_factory(project_config, read_only=False),
        "filesystem_project_ro": filesystem_factory(project_config, read_only=True),
        "shell_readonly": shell_factory(_SHELL_READONLY_RULES),
        "shell_file_ops": shell_factory(_SHELL_FILE_OPS_RULES),
        "dynamic_agents": _per_run_toolset(lambda: DynamicAgentsToolset()),
    }
