from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llm_do import (
    AttachmentPolicy,
    ApprovalController,
    ServerSideToolConfig,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerSpec,
    WorkerContext,
    WorkerRunResult,
    call_worker_async,
    create_worker,
)
from llm_do.delegation_toolset import DelegationToolset


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


def _create_toolset_and_context(context: WorkerContext):
    """Create a DelegationToolset and mock RunContext for testing."""
    toolsets = context.worker.toolsets or {}
    delegation_config = toolsets.get("delegation", {})
    toolset = DelegationToolset(config=delegation_config)

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
    """Sync helper to call DelegationToolset.call_tool for worker tools.

    This mimics the old context.delegate_sync() behavior for testing.
    Tool name is the same as worker name (no prefix).
    """
    toolset, mock_ctx = _create_toolset_and_context(context)

    # Tool name is the worker name directly (no prefix)
    tool_name = worker
    tool_args = {}
    if input_data is not None:
        # Convert input_data to string for the new API
        tool_args["input"] = str(input_data) if not isinstance(input_data, str) else input_data
    if attachments:
        tool_args["attachments"] = attachments

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
    parent = WorkerDefinition(name="parent", instructions="")
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
    asyncio.run(
        call_worker_async(
            registry=registry,
            worker="child",
            input_data={"task": "demo"},
            caller_context=context,
            attachments=[attachment],
            agent_runner=runner,
        )
    )

    assert seen_paths == [attachment.resolve()]


def test_call_worker_rejects_disallowed_attachments(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="")
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
        asyncio.run(
            call_worker_async(
                registry=registry,
                worker="child",
                input_data={"task": "demo"},
                caller_context=context,
                attachments=[bad_attachment],
            )
        )


def test_create_worker_defaults_include_toolset_config(tmp_path):
    registry = _registry(tmp_path)
    defaults = WorkerCreationDefaults(
        default_model="defaults-model",
        default_toolsets={"delegation": {"child": {}}},
    )

    spec = WorkerSpec(name="parent", instructions="delegate")
    parent = create_worker(registry, spec, defaults=defaults)
    assert parent.toolsets["delegation"]["child"] == {}

def test_worker_call_tool_respects_approval(monkeypatch, tmp_path):
    """Worker delegation goes through AgentToolset which checks approval via ApprovalToolset.

    In this test we verify the toolset calls call_worker_async when invoked.
    """
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"child": {}}},
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


def test_worker_call_requires_approval_for_generated_worker(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"worker_call": {}}},
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)
    registry.register_generated("child")

    toolset, mock_ctx = _create_toolset_and_context(context)

    result = toolset.needs_approval("worker_call", {"worker": "child"}, mock_ctx)

    assert result.is_needs_approval


def test_worker_call_blocks_non_generated_worker(tmp_path):
    """worker_call only works for session-generated workers, not configured ones."""
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"child": {}, "worker_call": {}}},
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    toolset, mock_ctx = _create_toolset_and_context(context)

    # Trying to call a configured worker via worker_call should fail
    # (configured workers should use their direct tool name instead)
    with pytest.raises(PermissionError, match="worker_call only supports session-generated workers"):
        asyncio.run(toolset.call_tool("worker_call", {"worker": "child"}, mock_ctx, None))

    # Trying to call an unknown worker should also fail
    with pytest.raises(PermissionError, match="worker_call only supports session-generated workers"):
        asyncio.run(toolset.call_tool("worker_call", {"worker": "unknown"}, mock_ctx, None))


def test_delegation_toolset_blocks_tool_name_collision(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"read_file": {}}, "filesystem": {}},
    )
    registry.save_definition(parent)
    registry.save_definition(WorkerDefinition(name="read_file", instructions=""))
    context = _parent_context(registry, parent)

    toolset, mock_ctx = _create_toolset_and_context(context)

    with pytest.raises(ValueError, match="conflict with other tool names"):
        asyncio.run(toolset.get_tools(mock_ctx))


def test_delegation_toolset_blocks_reserved_worker_name(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"worker_call": {}}},
    )
    registry.save_definition(parent)
    registry.save_definition(WorkerDefinition(name="worker_call", instructions=""))
    context = _parent_context(registry, parent)

    toolset, mock_ctx = _create_toolset_and_context(context)

    with pytest.raises(ValueError, match="reserved for delegation tools"):
        asyncio.run(toolset.get_tools(mock_ctx))
















def test_call_worker_propagates_cli_model(tmp_path):
    """cli_model from parent context should be passed to sub-workers."""
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="")
    child = WorkerDefinition(name="child", instructions="")
    registry.save_definition(parent)
    registry.save_definition(child)

    captured_cli_model = None

    def runner(defn, _input, ctx, _schema):
        nonlocal captured_cli_model
        captured_cli_model = ctx.cli_model
        return {"worker": defn.name}

    # Create parent context with cli_model set
    context = _parent_context(registry, parent)
    context.cli_model = "test-cli-model"

    asyncio.run(
        call_worker_async(
            registry=registry,
            worker="child",
            input_data={"task": "demo"},
            caller_context=context,
            agent_runner=runner,
        )
    )

    assert captured_cli_model == "test-cli-model"


def test_worker_create_tool_persists_definition(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="", toolsets={"delegation": {"worker_create": {}}})
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
        toolsets={"delegation": {"worker_create": {}}},
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


def test_worker_create_uses_output_dir_from_config(tmp_path):
    """worker_create saves to output_dir when configured."""
    registry = _registry(tmp_path)

    # Configure worker_create with a custom output_dir
    custom_output_dir = tmp_path / "custom_workers"
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={
            "delegation": {
                "worker_create": {
                    "output_dir": str(custom_output_dir),
                }
            }
        },
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    _create_worker_via_toolset(
        context,
        name="custom_child",
        instructions="custom worker",
        description="test output_dir",
    )

    # Verify worker was saved to the custom output_dir
    expected_path = custom_output_dir / "custom_child" / "worker.worker"
    assert expected_path.exists(), f"Expected worker at {expected_path}"

    # Verify content
    content = expected_path.read_text()
    assert "custom_child" in content
    assert "custom worker" in content


def test_worker_create_with_output_dir_ignores_default_generated_dir(tmp_path):
    """worker_create with output_dir doesn't conflict with workers in default generated_dir."""
    registry = _registry(tmp_path)

    # Create a worker with same name in the default generated_dir
    default_worker_dir = registry.generated_dir / "same_name"
    default_worker_dir.mkdir(parents=True)
    (default_worker_dir / "worker.worker").write_text(
        "---\nname: same_name\n---\nOld worker in default location",
        encoding="utf-8",
    )

    # Configure worker_create with a custom output_dir
    custom_output_dir = tmp_path / "custom_workers"
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={
            "delegation": {
                "worker_create": {
                    "output_dir": str(custom_output_dir),
                }
            }
        },
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    # Should NOT raise - custom output_dir is different from default generated_dir
    _create_worker_via_toolset(
        context,
        name="same_name",  # Same name as worker in default location
        instructions="new worker in custom location",
    )

    # Verify worker was saved to the custom output_dir
    expected_path = custom_output_dir / "same_name" / "worker.worker"
    assert expected_path.exists()
    content = expected_path.read_text()
    assert "new worker in custom location" in content


def test_worker_call_uses_workers_dir_from_config(tmp_path, monkeypatch):
    """worker_call looks in workers_dir when configured."""
    registry = _registry(tmp_path)

    # Create a worker in a custom directory
    custom_workers_dir = tmp_path / "custom_workers"
    worker_dir = custom_workers_dir / "my_worker"
    worker_dir.mkdir(parents=True)
    (worker_dir / "worker.worker").write_text(
        "---\nname: my_worker\n---\nTest worker",
        encoding="utf-8",
    )

    # Configure worker_call with workers_dir
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={
            "delegation": {
                "worker_call": {
                    "workers_dir": str(custom_workers_dir),
                }
            }
        },
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    # Mock call_worker_async to capture what worker path is passed
    captured_worker = None

    async def mock_call_worker(**kwargs):
        nonlocal captured_worker
        captured_worker = kwargs.get("worker")
        return WorkerRunResult(output="test output", messages=[])

    monkeypatch.setattr("llm_do.runtime.call_worker_async", mock_call_worker)

    toolset, mock_ctx = _create_toolset_and_context(context)

    # Call worker_call with a worker name
    asyncio.run(toolset.call_tool(
        "worker_call",
        {"worker": "my_worker"},
        mock_ctx,
        None,
    ))

    # Verify the full path was passed
    expected_path = str(custom_workers_dir / "my_worker" / "worker.worker")
    assert captured_worker == expected_path


def test_delegation_toolset_blocks_server_side_tool_collision(tmp_path):
    """Worker names cannot collide with server-side tool names (web_search, etc.)."""
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"web_search": {}}},
        server_side_tools=[ServerSideToolConfig(tool_type="web_search")],
    )
    registry.save_definition(parent)
    # Create a worker named web_search (collision)
    registry.save_definition(WorkerDefinition(name="web_search", instructions=""))
    context = _parent_context(registry, parent)

    toolset, mock_ctx = _create_toolset_and_context(context)

    with pytest.raises(ValueError, match="conflict with other tool names"):
        asyncio.run(toolset.get_tools(mock_ctx))


def test_delegation_toolset_allows_worker_when_no_server_side_collision(tmp_path):
    """Worker name web_search is allowed if server_side_tools doesn't include it."""
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"web_search": {}}},
        # No server_side_tools configured
    )
    registry.save_definition(parent)
    registry.save_definition(WorkerDefinition(name="web_search", instructions=""))
    context = _parent_context(registry, parent)

    toolset, mock_ctx = _create_toolset_and_context(context)

    # Should not raise - no collision since server_side_tools is empty
    tools = asyncio.run(toolset.get_tools(mock_ctx))
    assert "web_search" in tools


def test_worker_context_creation_defaults_never_none():
    """WorkerContext.creation_defaults should never be None."""
    from llm_do import WorkerDefinition, WorkerContext, ApprovalController

    # Without explicit creation_defaults
    worker = WorkerDefinition(name="test", instructions="test")
    controller = ApprovalController(mode="approve_all")

    ctx = WorkerContext(
        worker=worker,
        effective_model=None,
        approval_controller=controller,
    )
    assert ctx.creation_defaults is not None
    assert isinstance(ctx.creation_defaults, WorkerCreationDefaults)


def test_worker_context_creation_defaults_explicit_none_becomes_default():
    """Even if creation_defaults is explicitly set to None, __post_init__ fixes it."""
    from llm_do import WorkerDefinition, WorkerContext, ApprovalController

    worker = WorkerDefinition(name="test", instructions="test")
    controller = ApprovalController(mode="approve_all")

    # Explicitly pass None (unusual but should be handled)
    ctx = WorkerContext(
        worker=worker,
        effective_model=None,
        approval_controller=controller,
        creation_defaults=None,
    )
    assert ctx.creation_defaults is not None
    assert isinstance(ctx.creation_defaults, WorkerCreationDefaults)


def test_worker_create_without_explicit_defaults(tmp_path):
    """worker_create should work even without explicit creation_defaults."""
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"worker_create": {}}}
    )
    registry.save_definition(parent)

    # Create context without explicit defaults (uses default_factory)
    context = _parent_context(registry, parent, defaults=None)

    # Should not raise - creation_defaults is defaulted
    payload = _create_worker_via_toolset(
        context,
        name="new_worker",
        instructions="test instructions",
    )

    assert payload["name"] == "new_worker"
    created = registry.load_definition("new_worker")
    assert created.instructions == "test instructions"
