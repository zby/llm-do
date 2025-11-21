import pytest

from llm_do.pydanticai import ApprovalController, SandboxConfig, SandboxManager, SandboxToolset


def _make_toolset(root, *, mode="rw", allowed_suffixes=None, max_bytes=2_000_000):
    cfg = SandboxConfig(
        name="work",
        path=root,
        mode=mode,
        allowed_suffixes=allowed_suffixes or [],
        max_bytes=max_bytes,
    )
    manager = SandboxManager({"work": cfg})
    approvals = ApprovalController({}, requests=[])
    return manager, SandboxToolset(manager, approvals)


def test_sandbox_toolset_roundtrip(tmp_path):
    manager, toolset = _make_toolset(tmp_path / "sandbox")

    message = toolset.write_text("work", "note.txt", "hello")
    assert "wrote" in message

    listing = toolset.list("work")
    assert listing == ["note.txt"]

    assert toolset.read_text("work", "note.txt") == "hello"


def test_sandbox_manager_prevents_escape(tmp_path):
    manager, toolset = _make_toolset(tmp_path / "sandbox")
    (tmp_path / "sandbox" / "inside.txt").write_text("ok", encoding="utf-8")

    with pytest.raises(PermissionError):
        toolset.read_text("work", "../outside.txt")

    with pytest.raises(PermissionError):
        manager.write_text("work", "../escape.txt", "nope")


def test_sandbox_toolset_enforces_suffix_and_mode(tmp_path):
    manager, toolset = _make_toolset(tmp_path / "sandbox", allowed_suffixes=[".txt"])
    with pytest.raises(PermissionError):
        toolset.write_text("work", "note.md", "oops")

    ro_manager, ro_toolset = _make_toolset(tmp_path / "ro", mode="ro")
    (tmp_path / "ro").mkdir(parents=True, exist_ok=True)
    with pytest.raises(PermissionError):
        ro_toolset.write_text("work", "cant.txt", "blocked")


