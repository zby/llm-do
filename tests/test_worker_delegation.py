from __future__ import annotations

from pathlib import Path

import pytest

from llm_do.pydanticai import (
    AttachmentPolicy,
    ApprovalController,
    SandboxConfig,
    SandboxManager,
    SandboxToolset,
    WorkerCreationProfile,
    WorkerDefinition,
    WorkerRegistry,
    WorkerSpec,
    WorkerContext,
    call_worker,
    create_worker,
)


def _registry(tmp_path):
    root = tmp_path / "workers"
    return WorkerRegistry(root)


def _parent_context(registry, worker, profile=None):
    sandbox_manager = SandboxManager(worker.sandboxes)
    sandbox_toolset = SandboxToolset(sandbox_manager, ApprovalController({}, requests=[]))
    return WorkerContext(
        registry=registry,
        worker=worker,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_toolset,
        creation_profile=profile or WorkerCreationProfile(),
        effective_model="cli-model",
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
    profile = WorkerCreationProfile(
        default_model="profile-model",
        default_sandboxes={"shared": sandbox},
        default_allow_workers=["child"],
    )

    spec = WorkerSpec(name="parent", instructions="delegate")
    parent = create_worker(registry, spec, profile=profile)
    child = WorkerDefinition(name="child", instructions="")
    registry.save_definition(child)

    seen_sandboxes: list[str] = []

    def runner(defn, _input, ctx, _schema):
        seen_sandboxes.extend(ctx.sandbox_manager.sandboxes.keys())
        return {"worker": defn.name}

    context = _parent_context(registry, parent, profile=profile)
    call_worker(
        registry=registry,
        worker="child",
        input_data={"task": "demo"},
        caller_context=context,
        agent_runner=runner,
    )

    assert seen_sandboxes == ["shared"]
