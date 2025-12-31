from __future__ import annotations

from llm_do.ui.controllers import ExitConfirmationController, ExitDecision


def test_exit_confirmation_requires_two_requests() -> None:
    controller = ExitConfirmationController()
    assert controller.request() == ExitDecision.PROMPT
    assert controller.request() == ExitDecision.EXIT

    controller.reset()
    assert controller.request() == ExitDecision.PROMPT

