"""UI-agnostic controllers for the Textual TUI.

These components encapsulate stateful UI logic (history, approvals, etc.)
without depending on Textual, so they can be unit tested and reused by other
frontends.
"""

from .approval_workflow import ApprovalWorkflowController, PendingApproval
from .exit_confirmation import ExitConfirmationController, ExitDecision
from .input_history import HistoryNavigation, InputHistoryController
from .worker_runner import RunTurnFn, WorkerRunner

__all__ = [
    "ApprovalWorkflowController",
    "PendingApproval",
    "ExitConfirmationController",
    "ExitDecision",
    "InputHistoryController",
    "HistoryNavigation",
    "WorkerRunner",
    "RunTurnFn",
]
