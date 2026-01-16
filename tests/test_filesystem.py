from __future__ import annotations

from pydantic_ai_blocking_approval import ApprovalResult

import llm_do.toolsets.filesystem as filesystem_module


def test_needs_approval_short_circuits_blocked(monkeypatch) -> None:
    toolset = filesystem_module.FileSystemToolset(config={})

    def fake_needs_approval_from_config(name, config):
        return ApprovalResult.blocked("blocked by config")

    monkeypatch.setattr(
        filesystem_module,
        "needs_approval_from_config",
        fake_needs_approval_from_config,
    )

    result = toolset.needs_approval(
        "read_file",
        {"path": "example.txt"},
        None,
        config={"read_file": {"pre_approved": True}},
    )

    assert result.is_blocked
    assert result.block_reason == "blocked by config"


def test_needs_approval_short_circuits_pre_approved(monkeypatch) -> None:
    toolset = filesystem_module.FileSystemToolset(config={"write_approval": True})

    def fake_needs_approval_from_config(name, config):
        return ApprovalResult.pre_approved()

    monkeypatch.setattr(
        filesystem_module,
        "needs_approval_from_config",
        fake_needs_approval_from_config,
    )

    result = toolset.needs_approval(
        "write_file",
        {"path": "example.txt", "content": "data"},
        None,
        config={"write_file": {"pre_approved": False}},
    )

    assert result.is_pre_approved


def test_needs_approval_unknown_tool_requires_approval() -> None:
    toolset = filesystem_module.FileSystemToolset(config={"read_approval": False, "write_approval": False})

    result = toolset.needs_approval(
        "unknown_tool",
        {"path": "example.txt"},
        None,
        config=None,
    )

    assert result.is_needs_approval
