from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.runtime import build_registry


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
        )
