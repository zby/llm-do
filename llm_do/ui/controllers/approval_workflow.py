"""Approval queue and batching logic (UI-agnostic)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from pydantic_ai_blocking_approval import ApprovalRequest


@dataclass(frozen=True, slots=True)
class PendingApproval:
    request: ApprovalRequest
    queue_index: int
    queue_total: int


class ApprovalWorkflowController:
    """Queue of approval requests with stable batch numbering."""

    def __init__(self) -> None:
        self._queue: deque[ApprovalRequest] = deque()
        self._batch_total = 0
        self._batch_index = 0

    def has_pending(self) -> bool:
        return bool(self._queue)

    def enqueue(self, request: ApprovalRequest) -> PendingApproval:
        if not self._queue:
            self._batch_total = 0
            self._batch_index = 0
        self._queue.append(request)
        self._batch_total += 1
        current = self.current()
        if current is None:
            raise RuntimeError("enqueue() must produce a current approval")
        return current

    def current(self) -> PendingApproval | None:
        if not self._queue:
            return None
        return PendingApproval(
            request=self._queue[0],
            queue_index=self._batch_index + 1,
            queue_total=self._batch_total,
        )

    def pop_current(self) -> PendingApproval | None:
        """Advance to the next approval, returning the new current state."""
        if not self._queue:
            return None
        self._queue.popleft()
        self._batch_index += 1
        if self._queue:
            return self.current()
        self._batch_total = 0
        self._batch_index = 0
        return None

