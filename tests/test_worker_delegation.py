from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from llm_do import (
    AttachmentPolicy,
    ApprovalController,
    ApprovalDecision,
    RuntimeCreator,
    RuntimeDelegator,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerSpec,
    WorkerContext,
    WorkerRunResult,
    call_worker,
    create_worker,
)
from llm_do.worker_sandbox import (
    AttachmentValidator,
    Sandbox,
    SandboxConfig,
)
from llm_do.filesystem_sandbox import PathConfig, ReadResult
from llm_do.tool_approval import ApprovalRequest


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
    if worker.sandbox and worker.sandbox.paths:
        sandbox = Sandbox(worker.sandbox, base_path=registry.root)
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
        allow_workers=["child"],
        sandbox=SandboxConfig(paths={
            "input": PathConfig(
                root=str(sandbox_root),
                mode="ro",
                suffixes=[".pdf", ".txt"],
            )
        }),
        attachment_policy=attachment_policy or AttachmentPolicy(),
    )
    return parent, sandbox_root


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
    path_cfg = PathConfig(root=str(tmp_path / "shared"), mode="rw")
    defaults = WorkerCreationDefaults(
        default_model="defaults-model",
        default_sandbox=SandboxConfig(paths={"shared": path_cfg}),
        default_allow_workers=["child"],
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
    """Worker delegation always goes through approval controller.

    In the new architecture, RuntimeDelegator always creates an ApprovalRequest.
    The controller's mode determines if it prompts (interactive) or auto-approves.
    """
    registry = _registry(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        allow_workers=["child"],
    )
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    invoked = False

    def fake_call_worker(**_):
        nonlocal invoked
        invoked = True
        return WorkerRunResult(output={"ok": True})

    monkeypatch.setattr("llm_do.runtime.call_worker", fake_call_worker)

    # With default auto-approve callback, the tool executes
    result = RuntimeDelegator(context).call_sync(worker="child", input_data={"task": "demo"})

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

    def fake_call_worker(**kwargs):
        captured.update(kwargs)
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker", fake_call_worker)

    result = RuntimeDelegator(context).call_sync(
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
        RuntimeDelegator(context).call_sync(
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
        RuntimeDelegator(context).call_sync(
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
        RuntimeDelegator(context).call_sync(
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
        RuntimeDelegator(context).call_sync(
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
        RuntimeDelegator(context).call_sync(
            worker="child",
            input_data={"task": "demo"},
            attachments=["input/../secret.pdf"],
        )


def test_worker_call_tool_includes_attachment_metadata(monkeypatch, tmp_path):
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

    def fake_call_worker(**_):
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker", fake_call_worker)

    result = RuntimeDelegator(context).call_sync(
        worker="child",
        input_data={"task": "demo"},
        attachments=["input/deck.pdf"],
    )

    assert result == {"status": "ok"}

    # Should have 2 approval requests: sandbox.read (for attachment) + worker.call
    assert len(captured_requests) == 2

    # First should be sandbox.read for the attachment
    sandbox_read_request = captured_requests[0]
    assert sandbox_read_request.tool_name == "sandbox.read"
    assert sandbox_read_request.payload["path"] == "input/deck.pdf"
    assert sandbox_read_request.payload["bytes"] == len(payload_bytes)

    # Second should be worker.call with attachment metadata
    worker_call_request = captured_requests[1]
    assert worker_call_request.tool_name == "worker.call"
    attachment_info = worker_call_request.payload["attachments"][0]
    assert attachment_info["sandbox"] == "input"
    assert attachment_info["path"] == "deck.pdf"
    assert attachment_info["bytes"] == len(payload_bytes)


def test_worker_create_tool_persists_definition(tmp_path):
    registry = _registry(tmp_path)
    parent = WorkerDefinition(name="parent", instructions="")
    registry.save_definition(parent)
    context = _parent_context(registry, parent)

    payload = RuntimeCreator(context).create(
        name="child",
        instructions="delegate",
        description="desc",
    )

    created = registry.load_definition("child")
    assert created.instructions == "delegate"
    assert payload["name"] == "child"


def test_worker_create_tool_respects_approval(monkeypatch, tmp_path):
    """Worker creation always goes through approval controller.

    In the new architecture, RuntimeCreator always creates an ApprovalRequest.
    The controller's mode determines if it prompts (interactive) or auto-approves.
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
    result = RuntimeCreator(context).create(name="child", instructions="demo")

    # Tool executed successfully
    assert result["name"] == "child"
    assert result["instructions"] == "demo"
    assert invoked


def test_attachment_triggers_sandbox_read_approval(monkeypatch, tmp_path):
    """Test that attachments trigger sandbox.read approval before sharing."""
    registry = _registry(tmp_path)
    parent, sandbox_root = _parent_with_sandbox(tmp_path)
    # Add sandbox.read rule requiring approval (no longer used, kept for backwards compat)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        allow_workers=["child"],
        sandbox=parent.sandbox,
    )
    registry.save_definition(parent)

    # Track approval requests
    approval_requests = []

    def tracking_callback(request: ApprovalRequest) -> ApprovalDecision:
        approval_requests.append({"tool": request.tool_name, "payload": request.payload})
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

    def fake_call_worker(**kwargs):
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker", fake_call_worker)

    # Call with attachment
    RuntimeDelegator(context).call_sync(
        worker="child",
        input_data={"task": "analyze"},
        attachments=["input/secret.pdf"],
    )

    # Verify sandbox.read approval was requested
    sandbox_read_requests = [r for r in approval_requests if r["tool"] == "sandbox.read"]
    assert len(sandbox_read_requests) == 1

    req = sandbox_read_requests[0]
    assert req["payload"]["path"] == "input/secret.pdf"
    assert req["payload"]["target_worker"] == "child"
    assert req["payload"]["bytes"] == len(b"sensitive data")


def test_attachment_denied_by_sandbox_read_approval(monkeypatch, tmp_path):
    """Test that denying sandbox.read approval prevents attachment sharing."""
    registry = _registry(tmp_path)
    parent, sandbox_root = _parent_with_sandbox(tmp_path)
    parent = WorkerDefinition(
        name="parent",
        instructions="",
        allow_workers=["child"],
        sandbox=parent.sandbox,
    )
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

    def fake_call_worker(**kwargs):
        nonlocal call_invoked
        call_invoked = True
        return WorkerRunResult(output={"status": "ok"})

    monkeypatch.setattr("llm_do.runtime.call_worker", fake_call_worker)

    # Call should raise PermissionError
    with pytest.raises(PermissionError, match="sandbox.read"):
        RuntimeDelegator(context).call_sync(
            worker="child",
            input_data={"task": "analyze"},
            attachments=["input/secret.pdf"],
        )

    # Worker was never called
    assert not call_invoked
