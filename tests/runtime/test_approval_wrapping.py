from pydantic_ai_blocking_approval import ApprovalDecision, ApprovalToolset

from llm_do.ctx_runtime.cli import _wrap_toolsets_with_approval
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
