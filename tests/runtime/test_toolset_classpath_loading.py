from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.cli.main import build_entry
from llm_do.toolsets.shell import ShellToolset


@pytest.mark.anyio
async def test_build_entry_supports_toolset_class_paths(tmp_path: Path) -> None:
    worker = tmp_path / "main.worker"
    worker.write_text(
        """\
---
name: main
toolsets:
  llm_do.toolsets.shell.ShellToolset:
    default:
      approval_required: false
---
Hello
"""
    )

    entry = await build_entry([str(worker)], [], model="test-model")
    shell = next(ts for ts in entry.toolsets if isinstance(ts, ShellToolset))
    assert shell.config["default"]["approval_required"] is False

