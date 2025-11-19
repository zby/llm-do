from __future__ import annotations

import pytest

from llm_do.tools_files import Files


def test_files_list_and_read_write(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "one.txt").write_text("alpha", encoding="utf-8")
    files = Files("ro:" + str(sandbox))

    listing = files.list("*.txt")
    assert listing == ["one.txt"]

    content = files.read_text("one.txt")
    assert content == "alpha"

    writer = Files({"mode": "out", "path": sandbox, "alias": "custom"})
    message = writer.write_text("two.txt", "bravo")
    assert "wrote" in message
    assert (sandbox / "two.txt").read_text(encoding="utf-8") == "bravo"


def test_files_prevent_escape(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    files = Files("ro:" + str(sandbox))
    with pytest.raises(ValueError):
        files.read_text("../secret.txt")


def test_files_write_in_read_only(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    files = Files("ro:" + str(sandbox))
    with pytest.raises(PermissionError):
        files.write_text("blocked.txt", "oops")
