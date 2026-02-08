from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.project import build_registry
from llm_do.project.host_toolsets import (
    build_agent_toolset_factory,
    build_host_toolsets,
)
from llm_do.runtime.tooling import tool_def_name


def _host_registry_kwargs(project_root: Path) -> dict[str, object]:
    return {
        "extra_toolsets": build_host_toolsets(Path.cwd(), project_root),
        "agent_toolset_factory": build_agent_toolset_factory(),
    }


def _write_tools_module(path: Path) -> None:
    path.write_text(
        """\
from pydantic_ai.toolsets import FunctionToolset


def build_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def add(a: int, b: int) -> int:
        return a + b

    return tools


def ping() -> str:
    return "pong"

TOOLS = [ping]
TOOLSETS = {"calc_tools": build_tools}
""",
        encoding="utf-8",
    )


def test_build_registry_resolves_tools_and_toolsets(tmp_path: Path) -> None:
    tools_path = tmp_path / "tools.py"
    _write_tools_module(tools_path)

    agent_path = tmp_path / "main.agent"
    agent_path.write_text(
        """\
---
name: main
tools:
  - ping
toolsets:
  - calc_tools
---
Use tools.
""",
        encoding="utf-8",
    )

    registry = build_registry(
        [str(agent_path)],
        [str(tools_path)],
        project_root=tmp_path,
        **_host_registry_kwargs(tmp_path),
    )
    agent = registry.agents["main"]

    assert len(agent.tools) == 1
    assert tool_def_name(agent.tools[0]) == "ping"
    assert len(agent.toolsets) == 1


def test_build_registry_rejects_toolset_name_in_tools(tmp_path: Path) -> None:
    tools_path = tmp_path / "tools.py"
    tools_path.write_text(
        """\
from pydantic_ai.toolsets import FunctionToolset


def build_tools(_ctx):
    return FunctionToolset()

TOOLSETS = {"dup_name": build_tools}
""",
        encoding="utf-8",
    )

    agent_path = tmp_path / "main.agent"
    agent_path.write_text(
        """\
---
name: main
tools:
  - dup_name
---
Use tools.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown tool"):
        build_registry(
            [str(agent_path)],
            [str(tools_path)],
            project_root=tmp_path,
            **_host_registry_kwargs(tmp_path),
        )
