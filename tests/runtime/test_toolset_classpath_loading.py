from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.runtime import build_entry


@pytest.mark.anyio
async def test_build_entry_rejects_unregistered_toolsets(tmp_path: Path) -> None:
    worker = tmp_path / "main.worker"
    worker.write_text(
        """\
---
name: main
entry: true
toolsets:
  - unknown_toolset
---
Hello
"""
    )

    with pytest.raises(ValueError, match="Unknown toolset"):
        build_entry(
            [str(worker)],
            [],
        )
