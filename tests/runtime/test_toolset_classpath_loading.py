from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.runtime import build_invocable_registry
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

    registry = await build_invocable_registry(
        [str(worker)],
        [],
        entry_name="main",
        entry_model_override="test-model",
    )
    entry = registry.get("main")
    shell = next(ts for ts in entry.toolsets if isinstance(ts, ShellToolset))
    assert shell.config["default"]["approval_required"] is False
