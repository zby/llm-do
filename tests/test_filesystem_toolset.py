from __future__ import annotations

import pytest

from llm_do.filesystem_toolset import FileSystemToolset


@pytest.mark.parametrize("read_approval,expected_needs_approval", [
    (True, True),
    (False, False),
])
def test_list_files_approval_respects_config(read_approval, expected_needs_approval):
    toolset = FileSystemToolset(config={"read_approval": read_approval})
    result = toolset.needs_approval("list_files", {"path": "."}, None)
    assert result.is_needs_approval == expected_needs_approval
