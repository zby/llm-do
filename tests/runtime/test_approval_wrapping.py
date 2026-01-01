from pydantic_ai.settings import ModelSettings
from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalToolset

from llm_do.ctx_runtime.approval_wrappers import _wrap_toolsets_with_approval
from llm_do.ctx_runtime.invocables import WorkerInvocable
from llm_do.toolsets.filesystem import FileSystemToolset


def test_wraps_nested_toolsets_inside_pre_wrapped_worker() -> None:
    def callback_primary(_request):
        return ApprovalDecision(approved=True)

    def callback_other(_request):
        return ApprovalDecision(approved=False)

    worker = WorkerInvocable(
        name="child",
        instructions="Child worker",
        toolsets=[FileSystemToolset(config={})],
    )
    pre_wrapped = ApprovalToolset(inner=worker, approval_callback=callback_primary)

    wrapped = _wrap_toolsets_with_approval(
        [pre_wrapped],
        approval_callback=callback_other,
        return_permission_errors=False,
    )

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    assert wrapped[0]._approval_callback is callback_primary
    inner = wrapped[0]._inner
    assert isinstance(inner, WorkerInvocable)
    assert inner.toolsets
    assert isinstance(inner.toolsets[0], ApprovalToolset)


def test_wrap_preserves_worker_fields() -> None:
    def callback(_request):
        return ApprovalDecision(approved=True)

    model_settings = ModelSettings(temperature=0.2)
    worker = WorkerInvocable(
        name="child",
        instructions="Child worker",
        toolsets=[FileSystemToolset(config={})],
        model_settings=model_settings,
    )

    wrapped = _wrap_toolsets_with_approval(
        [worker],
        approval_callback=callback,
        return_permission_errors=False,
    )

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner = wrapped[0]._inner
    assert isinstance(inner, WorkerInvocable)
    assert inner.model_settings == model_settings


def test_wrap_handles_worker_cycles() -> None:
    def callback(_request):
        return ApprovalDecision(approved=True)

    worker_a = WorkerInvocable(name="worker_a", instructions="A")
    worker_b = WorkerInvocable(name="worker_b", instructions="B")
    worker_a.toolsets = [worker_b]
    worker_b.toolsets = [worker_a]

    wrapped = _wrap_toolsets_with_approval(
        [worker_a],
        approval_callback=callback,
        return_permission_errors=False,
    )

    assert len(wrapped) == 1
    assert isinstance(wrapped[0], ApprovalToolset)
    inner_a = wrapped[0]._inner
    assert isinstance(inner_a, WorkerInvocable)
    assert isinstance(inner_a.toolsets[0], ApprovalToolset)
    inner_b = inner_a.toolsets[0]._inner
    assert isinstance(inner_b, WorkerInvocable)
    assert isinstance(inner_b.toolsets[0], ApprovalToolset)
    assert inner_b.toolsets[0]._inner is inner_a
