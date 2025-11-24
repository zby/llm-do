from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.pydanticai import (
    AttachmentPolicy,
    ApprovalController,
    SandboxConfig,
    SandboxManager,
    SandboxToolset,
    ToolRule,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerSpec,
    WorkerContext,
    WorkerRunResult,
    call_worker,
    create_worker,
)
from llm_do.pydanticai.base import _worker_call_tool, _worker_create_tool


def _registry(tmp_path):
    root = tmp_path / "workers"
    return WorkerRegistry(root)


def _parent_context(registry, worker, defaults=None):
    controller = ApprovalController(worker.tool_rules)
    sandbox_manager = SandboxManager(worker.sandboxes)
    sandbox_toolset = SandboxToolset(sandbox_manager, controller)
    worker_path = registry._definition_path(worker.name)
    return WorkerContext(
        registry=registry,
        worker=worker,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_toolset,
        creation_defaults=defaults or WorkerCreationDefaults(),
        effective_model="cli-model",
        approval_controller=controller,
        worker_path=worker_path,
        project_root=worker_path.parent,
    )


def test_call_worker_forwards_attachments(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="", allow_workers=["child"])
    child = WorkerDefinition(
        name="child",
        instructions="",
        attachment_policy=AttachmentPolicy(allowed_suffixes=[".txt"]),
    )
    registry.save_definition(parent)
    registry.save_definition(child)

    attachment = tmp_path / "note.txt"
    attachment.write_text("memo", encoding="utf-8")

    seen_paths: list[Path] = []

    def runner(defn, _input, ctx, _schema):
        seen_paths.extend(ctx.attachments)
        return {"worker": defn.name}

    context = _parent_context(registry, parent)
    call_worker(
        registry=registry,
        worker="child",
        input_data={"task": "demo"},
        caller_context=context,
        attachments=[attachment],
        agent_runner=runner,
    )

    assert seen_paths == [attachment.resolve()]


def test_call_worker_rejects_disallowed_attachments(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="", allow_workers=["child"])
    child = WorkerDefinition(
        name="child",
        instructions="",
        attachment_policy=AttachmentPolicy(allowed_suffixes=[".txt"]),
    )
    registry.save_definition(parent)
    registry.save_definition(child)

    bad_attachment = tmp_path / "data.pdf"
    bad_attachment.write_text("blocked", encoding="utf-8")

    context = _parent_context(registry, parent)
    with pytest.raises(ValueError):
        call_worker(
            registry=registry,
            worker="child",
            input_data={"task": "demo"},
            caller_context=context,
            attachments=[bad_attachment],
        )


def test_create_worker_defaults_allow_delegation(tmp_path):
    registry = _registry(tmp_path)
    sandbox = SandboxConfig(name="shared", path=tmp_path / "shared", mode="rw")
    defaults = WorkerCreationDefaults(
        default_model="defaults-model",
        default_sandboxes={"shared": sandbox},
        default_allow_workers=["child"],
    )

    spec = WorkerSpec(name="parent", instructions="delegate")
    parent = create_worker(registry, spec, defaults=defaults)
    child = WorkerDefinition(name="child", instructions="")
    registry.save_definition(child)

    seen_sandboxes: list[str] = []

    def runner(defn, _input, ctx, _schema):
        seen_sandboxes.extend(ctx.sandbox_manager.sandboxes.keys())
        return {"worker": defn.name}

    context = _parent_context(registry, parent, defaults=defaults)
    call_worker(
        registry=registry,
        worker="child",
        input_data={"task": "demo"},
        caller_context=context,
        agent_runner=runner,
    )

    assert seen_sandboxes == ["shared"]

def test_worker_call_tool_respects_approval(monkeypatch, tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        allow_workers=["child"],
        tool_rules={"worker.call": ToolRule(name="worker.call", approval_required=True)},
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    invoked = False

    def fake_call_worker(**_):
        nonlocal invoked
        invoked = True
        return WorkerRunResult(output={"ok": True})

    monkeypatch.setattr("llm_do.pydanticai.base.call_worker", fake_call_worker)

    # With default auto-approve callback, the tool executes
    result = _worker_call_tool(context, worker="child", input_data={"task": "demo"})

    # Tool executed successfully
    assert result == {"ok": True}
    assert invoked


def test_worker_call_tool_passes_attachments(monkeypatch, tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="", allow_workers=["child"])
    registry.save_definition(parent)
    context = _parent_context(registry, parent)
    attachment = tmp_path / "note.txt"
    attachment.write_text("memo", encoding="utf-8")

    captured = {}

    def fake_call_worker(**kwargs):
        captured.update(kwargs)
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.pydanticai.base.call_worker", fake_call_worker)

    result = _worker_call_tool(
        context,
        worker="child",
        input_data={"task": "demo"},
        attachments=[str(attachment)],
    )

    assert result == {"status": "ok"}
    assert captured["attachments"] == [attachment.resolve()]


def test_worker_create_tool_persists_definition(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="")
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    payload = _worker_create_tool(
        context,
        name="child",
        instructions="delegate",
        description="desc",
    )

    created = registry.load_definition("child")
    assert created.instructions == "delegate"
    assert payload["name"] == "child"


def test_worker_create_tool_respects_approval(monkeypatch, tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        tool_rules={"worker.create": ToolRule(name="worker.create", approval_required=True)},
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    invoked = False

    class DummyDefinition:
        def __init__(self, payload):
            self.payload = payload

        def model_dump(self, mode="python"):
            return self.payload

    def fake_create_worker(**kwargs):
        nonlocal invoked
        invoked = True
        return DummyDefinition(kwargs["spec"].model_dump(mode="json"))

    monkeypatch.setattr("llm_do.pydanticai.base.create_worker", fake_create_worker)

    # With default auto-approve callback, the tool executes
    result = _worker_create_tool(context, name="child", instructions="demo")

    # Tool executed successfully
    assert result["name"] == "child"
    assert result["instructions"] == "demo"
    assert invoked
