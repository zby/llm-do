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
from llm_do.delegation_toolset import DelegationToolset
from llm_do.worker_sandbox import (
    AttachmentValidator,
    Sandbox,
    SandboxConfig,
)
# DelegationToolsetConfig no longer needed - using dict config
from pydantic_ai_filesystem_sandbox import PathConfig, ReadResult
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

    # Create new sandbox from worker definition
    sandbox_config = worker.sandbox
    if sandbox_config and sandbox_config.paths:
        sandbox = Sandbox(sandbox_config, base_path=registry.root)
    else:
        sandbox = Sandbox(SandboxConfig(), base_path=registry.root)
    attachment_validator = AttachmentValidator(sandbox)
    return WorkerContext(
        registry=registry,
        worker=worker,
        attachment_validator=attachment_validator,
        creation_defaults=defaults or WorkerCreationDefaults(),
        effective_model="cli-model",
        approval_controller=controller,
        sandbox=sandbox,
    )


def _parent_with_sandbox(
    tmp_path,
    *,
    attachment_policy: AttachmentPolicy | None = None,
    text_suffixes: list[str] | None = None,
    attachment_suffixes: list[str] | None = None,
):
    sandbox_root = tmp_path / "input"
    sandbox_root.mkdir()
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        sandbox=SandboxConfig(paths={
            "input": PathConfig(
                root=str(sandbox_root),
                mode="ro",
                suffixes=[".pdf", ".txt"],
            )
        }),
        toolsets={"delegation": {"allow_workers": ["child"]}},
        attachment_policy=attachment_policy or AttachmentPolicy(),
    )
    return parent, sandbox_root


def _create_toolset_and_context(context: WorkerContext):
    """Create a DelegationToolset and mock RunContext for testing."""
    toolsets = context.worker.toolsets or {}
    delegation_config = toolsets.get("delegation", {"allow_workers": []})
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
    """Sync helper to call DelegationToolset.call_tool for worker_call.

    This mimics the old context.delegate_sync() behavior for testing.
    """
    toolset, mock_ctx = _create_toolset_and_context(context)

    tool_args = {"worker": worker}
    if input_data is not None:
        tool_args["input_data"] = input_data
    if attachments:
        tool_args["attachments"] = attachments

    return asyncio.run(toolset.call_tool("worker_call", tool_args, mock_ctx, None))


def _create_worker_via_toolset(
    context: WorkerContext,
    name: str,
    instructions: str,
    description: str | None = None,
    model: str | None = None,
    output_schema_ref: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Sync helper to call DelegationToolset.call_tool for worker_create."""
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
    path_cfg = PathConfig(root=str(tmp_path / "shared"), mode="rw")
    defaults = WorkerCreationDefaults(
        default_model="defaults-model",
        default_sandbox=SandboxConfig(paths={"shared": path_cfg}),
        default_toolsets={"delegation": {"allow_workers": ["child"]}},
    )

    spec = WorkerSpec(name="parent", instructions="delegate")
    parent = create_worker(registry, spec, defaults=defaults)
    child = WorkerDefinition(name="child", instructions="")
    registry.save_definition(child)

    def runner(defn, _input, ctx, _schema):
        # Child worker inherits parent's defaults (including default_sandbox)
        # The new Sandbox (not visible in ctx) will have the "shared" path
        # The legacy sandbox_manager is always empty now for backward compatibility
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
    """Worker delegation goes through DelegationToolset which checks approval via ApprovalToolset.

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


def test_worker_call_tool_passes_attachments(monkeypatch, tmp_path):
    registry = _registry(tmp_path)
    parent, sandbox_root = _parent_with_sandbox(tmp_path)
    registry.save_definition(parent)
    context = _parent_context(registry, parent)
    attachment = sandbox_root / "deck.pdf"
    attachment.write_text("memo", encoding="utf-8")

    captured = {}

    async def fake_call_worker_async(**kwargs):
        captured.update(kwargs)
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker_async", fake_call_worker_async)

    result = _delegate_sync(
        context,
        worker="child",
        input_data={"task": "demo"},
        attachments=["input/deck.pdf"],
    )

    assert result == {"status": "ok"}
    delegated = captured["attachments"]
    assert len(delegated) == 1
    assert delegated[0].path == attachment.resolve()
    assert delegated[0].display_name == "input/deck.pdf"


def test_worker_call_tool_rejects_disallowed_sandbox_attachment(tmp_path):
    registry = _registry(tmp_path)
    # Use AttachmentPolicy to restrict attachment suffixes (not sandbox config)
    policy = AttachmentPolicy(allowed_suffixes=[".pdf"])
    parent, sandbox_root = _parent_with_sandbox(tmp_path, attachment_policy=policy)
    registry.save_definition(parent)
    child = WorkerDefinition(name="child", instructions="", model="test")
    registry.save_definition(child)
    context = _parent_context(registry, parent)
    disallowed = sandbox_root / "note.txt"
    disallowed.write_text("memo", encoding="utf-8")

    with pytest.raises(ValueError, match="Attachment suffix '.txt' not allowed"):
        _delegate_sync(
            context,
            worker="child",
            input_data={"task": "demo"},
            attachments=["input/note.txt"],
        )


def test_worker_call_tool_parent_policy_suffix(tmp_path):
    registry = _registry(tmp_path)
    policy = AttachmentPolicy(allowed_suffixes=[".txt"])
    parent, sandbox_root = _parent_with_sandbox(tmp_path, attachment_policy=policy)
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    pdf_path = sandbox_root / "deck.pdf"
    pdf_path.write_text("memo", encoding="utf-8")

    with pytest.raises(ValueError):
        _delegate_sync(
            context,
            worker="child",
            input_data={"task": "demo"},
            attachments=["input/deck.pdf"],
        )


def test_worker_call_tool_parent_policy_counts(tmp_path):
    registry = _registry(tmp_path)
    policy = AttachmentPolicy(max_attachments=1)
    parent, sandbox_root = _parent_with_sandbox(tmp_path, attachment_policy=policy)
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    for idx in range(2):
        path = sandbox_root / f"deck-{idx}.pdf"
        path.write_text("memo", encoding="utf-8")

    with pytest.raises(ValueError):
        _delegate_sync(
            context,
            worker="child",
            input_data={"task": "demo"},
            attachments=["input/deck-0.pdf", "input/deck-1.pdf"],
        )


def test_worker_call_tool_parent_policy_bytes(tmp_path):
    registry = _registry(tmp_path)
    policy = AttachmentPolicy(max_total_bytes=4)
    parent, sandbox_root = _parent_with_sandbox(tmp_path, attachment_policy=policy)
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    path = sandbox_root / "deck.pdf"
    path.write_text("12345", encoding="utf-8")

    with pytest.raises(ValueError):
        _delegate_sync(
            context,
            worker="child",
            input_data={"task": "demo"},
            attachments=["input/deck.pdf"],
        )


def test_worker_call_tool_rejects_path_escape(tmp_path):
    registry = _registry(tmp_path)
    parent, sandbox_root = _parent_with_sandbox(tmp_path)
    registry.save_definition(parent)
    context = _parent_context(registry, parent)
    outside = tmp_path / "secret.pdf"
    outside.write_text("memo", encoding="utf-8")

    with pytest.raises(PermissionError):
        _delegate_sync(
            context,
            worker="child",
            input_data={"task": "demo"},
            attachments=["input/../secret.pdf"],
        )


def test_worker_call_tool_includes_attachment_metadata(monkeypatch, tmp_path):
    """Test that sandbox.read approval is requested with attachment metadata."""
    registry = _registry(tmp_path)
    parent, sandbox_root = _parent_with_sandbox(tmp_path)
    registry.save_definition(parent)
    # Capture approval requests via callback
    captured_requests: list[ApprovalRequest] = []

    def capture_callback(request: ApprovalRequest) -> ApprovalDecision:
        captured_requests.append(request)
        return ApprovalDecision(approved=True)

    context = _parent_context(registry, parent, approval_callback=capture_callback)
    attachment = sandbox_root / "deck.pdf"
    payload_bytes = "memo".encode("utf-8")
    attachment.write_bytes(payload_bytes)

    async def fake_call_worker_async(**_):
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker_async", fake_call_worker_async)

    result = _delegate_sync(
        context,
        worker="child",
        input_data={"task": "demo"},
        attachments=["input/deck.pdf"],
    )

    assert result == {"status": "ok"}

    # Should have 1 approval request: sandbox.read (for attachment)
    # Note: worker.call approval is now handled by ApprovalToolset wrapper, not here
    assert len(captured_requests) == 1

    # Should be sandbox.read for the attachment
    sandbox_read_request = captured_requests[0]
    assert sandbox_read_request.tool_name == "sandbox.read"
    assert sandbox_read_request.tool_args["path"] == "input/deck.pdf"
    assert sandbox_read_request.tool_args["bytes"] == len(payload_bytes)


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
    """Worker creation goes through DelegationToolset.

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


def test_attachment_triggers_sandbox_read_approval(monkeypatch, tmp_path):
    """Test that attachments trigger sandbox.read approval before sharing."""
    registry = _registry(tmp_path)
    parent, sandbox_root = _parent_with_sandbox(tmp_path)
    registry.save_definition(parent)

    # Track approval requests
    approval_requests = []

    def tracking_callback(request: ApprovalRequest) -> ApprovalDecision:
        approval_requests.append({"tool": request.tool_name, "tool_args": request.tool_args})
        return ApprovalDecision(approved=True)

    controller = ApprovalController(mode="interactive", approval_callback=tracking_callback)
    sandbox = Sandbox(parent.sandbox, base_path=registry.root)
    attachment_validator = AttachmentValidator(sandbox)

    context = WorkerContext(
        registry=registry,
        worker=parent,
        attachment_validator=attachment_validator,
        creation_defaults=WorkerCreationDefaults(),
        effective_model="cli-model",
        approval_controller=controller,
        sandbox=sandbox,
    )

    # Create test file
    attachment = sandbox_root / "secret.pdf"
    attachment.write_bytes(b"sensitive data")

    async def fake_call_worker_async(**kwargs):
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker_async", fake_call_worker_async)

    # Call with attachment
    _delegate_sync(
        context,
        worker="child",
        input_data={"task": "analyze"},
        attachments=["input/secret.pdf"],
    )

    # Verify sandbox.read approval was requested
    sandbox_read_requests = [r for r in approval_requests if r["tool"] == "sandbox.read"]
    assert len(sandbox_read_requests) == 1

    req = sandbox_read_requests[0]
    assert req["tool_args"]["path"] == "input/secret.pdf"
    assert req["tool_args"]["target_worker"] == "child"
    assert req["tool_args"]["bytes"] == len(b"sensitive data")


def test_attachment_denied_by_sandbox_read_approval(monkeypatch, tmp_path):
    """Test that denying sandbox.read approval prevents attachment sharing."""
    registry = _registry(tmp_path)
    parent, sandbox_root = _parent_with_sandbox(tmp_path)
    registry.save_definition(parent)

    # Deny approval
    def denying_callback(request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=False, note="User denied")

    controller = ApprovalController(mode="interactive", approval_callback=denying_callback)
    sandbox = Sandbox(parent.sandbox, base_path=registry.root)
    attachment_validator = AttachmentValidator(sandbox)

    context = WorkerContext(
        registry=registry,
        worker=parent,
        attachment_validator=attachment_validator,
        creation_defaults=WorkerCreationDefaults(),
        effective_model="cli-model",
        approval_controller=controller,
        sandbox=sandbox,
    )

    # Create test file
    attachment = sandbox_root / "secret.pdf"
    attachment.write_bytes(b"sensitive data")

    call_invoked = False

    async def fake_call_worker_async(**kwargs):
        nonlocal call_invoked
        call_invoked = True
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker_async", fake_call_worker_async)

    # Call should raise PermissionError
    with pytest.raises(PermissionError, match="sandbox.read"):
        _delegate_sync(
            context,
            worker="child",
            input_data={"task": "analyze"},
            attachments=["input/secret.pdf"],
        )

    # Worker was never called
    assert not call_invoked
