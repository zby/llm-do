from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_do.toolsets.filesystem import FileSystemToolset
from llm_do.toolsets.shell import ShellToolset


@pytest.mark.anyio
async def test_shell_args_validator_requires_command() -> None:
    toolset = ShellToolset(config={"default": {"approval_required": False}})
    tool = (await toolset.get_tools(None))["shell"]
    with pytest.raises(ValidationError):
        tool.args_validator.validate_python({})


@pytest.mark.anyio
async def test_shell_args_validator_returns_defaults() -> None:
    toolset = ShellToolset(config={"default": {"approval_required": False}})
    tool = (await toolset.get_tools(None))["shell"]
    args = tool.args_validator.validate_python({"command": "ls"})
    assert args["command"] == "ls"
    assert args["timeout"] == 30


@pytest.mark.anyio
async def test_filesystem_read_requires_path() -> None:
    toolset = FileSystemToolset(config={})
    tool = (await toolset.get_tools(None))["read_file"]
    with pytest.raises(ValidationError):
        tool.args_validator.validate_python({})

