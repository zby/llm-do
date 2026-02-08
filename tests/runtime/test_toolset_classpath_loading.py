from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.project import build_registry
from llm_do.project.host_toolsets import (
    build_agent_toolset_factory,
    build_host_toolsets,
)


def _host_registry_kwargs(project_root: Path) -> dict[str, object]:
    return {
        "extra_toolsets": build_host_toolsets(Path.cwd(), project_root),
        "agent_toolset_factory": build_agent_toolset_factory(),
    }


@pytest.mark.anyio
async def test_build_registry_rejects_unregistered_toolsets(tmp_path: Path) -> None:
    worker = tmp_path / "main.agent"
    worker.write_text(
        """\
---
name: main
toolsets:
  - unknown_toolset
---
Hello
"""
    )

    with pytest.raises(ValueError, match="Unknown toolset"):
        build_registry(
            [str(worker)],
            [],
            project_root=tmp_path,
            **_host_registry_kwargs(tmp_path),
        )


@pytest.mark.anyio
async def test_build_registry_rejects_unregistered_tools(tmp_path: Path) -> None:
    worker = tmp_path / "main.agent"
    worker.write_text(
        """\
---
name: main
tools:
  - unknown_tool
---
Hello
"""
    )

    with pytest.raises(ValueError, match="Unknown tool"):
        build_registry(
            [str(worker)],
            [],
            project_root=tmp_path,
            **_host_registry_kwargs(tmp_path),
        )
