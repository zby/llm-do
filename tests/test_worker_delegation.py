from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llm_do import (
    AttachmentPolicy,
    ApprovalController,
    ApprovalDecision,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerSpec,
    WorkerContext,
    WorkerRunResult,
    call_worker,
    create_worker,
)
from llm_do.agent_toolset import AgentToolset
from pydantic_ai_blocking_approval import ApprovalRequest


def _registry(tmp_path):
    root = tmp_path / "workers"
    # Use test-specific generated dir (not global /tmp/llm-do/generated)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir(exist_ok=True)
    return WorkerRegistry(root, generated_dir=generated_dir)


def _parent_context(registry, worker, defaults=None, approval_callback=None):
    """Create a parent WorkerContext for testing.

    Args:
        registry: WorkerRegistry instance
        worker: WorkerDefinition for the parent
        defaults: Optional WorkerCreationDefaults
        approval_callback: Optional callback for approval requests.
                          If None, uses approve_all mode.
    """
    if approval_callback:
        controller = ApprovalController(mode="interactive", approval_callback=approval_callback)
    else:
        controller = ApprovalController(mode="approve_all")

    return WorkerContext(
        # Core
        worker=worker,
        effective_model="cli-model",
        approval_controller=controller,
        # Delegation
        registry=registry,
        creation_defaults=defaults or WorkerCreationDefaults(),
    )


def _parent_with_attachment_policy(
    tmp_path,
    *,
    attachment_policy: AttachmentPolicy | None = None,
):
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"allow_workers": ["child"]}},
        attachment_policy=attachment_policy or AttachmentPolicy(),
    )
    return parent


def _create_toolset_and_context(context: WorkerContext):
    """Create an AgentToolset and mock RunContext for testing."""
    toolsets = context.worker.toolsets or {}
    delegation_config = toolsets.get("delegation", {"allow_workers": []})
    toolset = AgentToolset(config=delegation_config)

    # Create mock RunContext with deps=context
    mock_ctx = MagicMock()
    mock_ctx.deps = context

    return toolset, mock_ctx


def _delegate_sync(
    context: WorkerContext,
    worker: str,
    input_data: Any = None,
    attachments: list[str] | None = None,
) -> Any:
    """Sync helper to call AgentToolset.call_tool for agent tools.

    This mimics the old context.delegate_sync() behavior for testing.
    Uses the new _agent_{worker} tool name format.
    """
    toolset, mock_ctx = _create_toolset_and_context(context)

    # New format: input as string, tool name is _agent_{worker}
    tool_name = f"_agent_{worker}"
    tool_args = {}
    if input_data is not None:
        # Convert input_data to string for the new API
        tool_args["input"] = str(input_data) if not isinstance(input_data, str) else input_data

    return asyncio.run(toolset.call_tool(tool_name, tool_args, mock_ctx, None))


def _create_worker_via_toolset(
    context: WorkerContext,
    name: str,
    instructions: str,
    description: str | None = None,
    model: str | None = None,
    output_schema_ref: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Sync helper to call AgentToolset.call_tool for worker_create."""
    toolset, mock_ctx = _create_toolset_and_context(context)

    tool_args = {"name": name, "instructions": instructions}
    if description:
        tool_args["description"] = description
    if model:
        tool_args["model"] = model
    if output_schema_ref:
        tool_args["output_schema_ref"] = output_schema_ref
    if force:
        tool_args["force"] = force

    return asyncio.run(toolset.call_tool("worker_create", tool_args, mock_ctx, None))


def test_call_worker_forwards_attachments(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="", toolsets={"delegation": {"allow_workers": ["child"]}})
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
        seen_paths.extend(att.path for att in ctx.attachments)
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
    parent = WorkerDefinition(name="parent", instructions="", toolsets={"delegation": {"allow_workers": ["child"]}})
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
    defaults = WorkerCreationDefaults(
        default_model="defaults-model",
        default_toolsets={"delegation": {"allow_workers": ["child"]}},
    )

    spec = WorkerSpec(name="parent", instructions="delegate")
    parent = create_worker(registry, spec, defaults=defaults)
    child = WorkerDefinition(name="child", instructions="")
    registry.save_definition(child)

    def runner(defn, _input, ctx, _schema):
        return {"worker": defn.name}

    context = _parent_context(registry, parent, defaults=defaults)
    result = call_worker(
        registry=registry,
        worker="child",
        input_data={"task": "demo"},
        caller_context=context,
        agent_runner=runner,
    )

    # Verify delegation succeeded
    assert result.output["worker"] == "child"

def test_worker_call_tool_respects_approval(monkeypatch, tmp_path):
    """Worker delegation goes through AgentToolset which checks approval via ApprovalToolset.

    In this test we verify the toolset calls call_worker_async when invoked.
    """
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"allow_workers": ["child"]}},
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    invoked = False

    async def fake_call_worker_async(**_):
        nonlocal invoked
        invoked = True
        return WorkerRunResult(output={"ok": True})

    monkeypatch.setattr("llm_do.runtime.call_worker_async", fake_call_worker_async)

    # With default auto-approve callback, the tool executes
    result = _delegate_sync(context, worker="child", input_data={"task": "demo"})

    # Tool executed successfully
    assert result == {"ok": True}
    assert invoked
















def test_worker_create_tool_persists_definition(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="")
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    payload = _create_worker_via_toolset(
        context,
        name="child",
        instructions="delegate",
        description="desc",
    )

    created = registry.load_definition("child")
    assert created.instructions == "delegate"
    assert payload["name"] == "child"


def test_worker_create_tool_respects_approval(monkeypatch, tmp_path):
    """Worker creation goes through AgentToolset.

    In this test we verify the toolset calls create_worker when invoked.
    """
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
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

    monkeypatch.setattr("llm_do.runtime.create_worker", fake_create_worker)

    # With default auto-approve callback, the tool executes
    result = _create_worker_via_toolset(context, name="child", instructions="demo")

    # Tool executed successfully
    assert result["name"] == "child"
    assert result["instructions"] == "demo"
    assert invoked




