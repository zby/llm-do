from __future__ import annotations

from pydantic_ai_blocking_approval import ApprovalRequest

from llm_do.ui.controllers import ApprovalWorkflowController


def test_approval_workflow_batches_and_resets() -> None:
    approvals = ApprovalWorkflowController()

    first = approvals.enqueue(
        ApprovalRequest(tool_name="t1", tool_args={"a": 1}, description="first")
    )
    assert first.queue_index == 1
    assert first.queue_total == 1

    # Total updates as more approvals arrive in the batch.
    current = approvals.enqueue(
        ApprovalRequest(tool_name="t2", tool_args={"b": 2}, description="second")
    )
    assert current.request.tool_name == "t1"
    assert current.queue_index == 1
    assert current.queue_total == 2

    current = approvals.pop_current()
    assert current is not None
    assert current.request.tool_name == "t2"
    assert current.queue_index == 2
    assert current.queue_total == 2

    assert approvals.pop_current() is None
    assert approvals.has_pending() is False

    # New batch resets numbering.
    current = approvals.enqueue(
        ApprovalRequest(tool_name="t3", tool_args={}, description="third")
    )
    assert current.queue_index == 1
    assert current.queue_total == 1
