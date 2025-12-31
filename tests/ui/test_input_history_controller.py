from __future__ import annotations

from llm_do.ui.controllers import InputHistoryController


def test_input_history_previous_no_entries() -> None:
    history = InputHistoryController()
    nav = history.previous("draft")
    assert nav.handled is False
    assert nav.text is None


def test_input_history_navigation_round_trip() -> None:
    history = InputHistoryController()
    history.record_submission("one")
    history.record_submission("two")

    nav = history.previous("draft")
    assert nav.handled is True
    assert nav.text == "two"

    nav = history.previous("ignored")
    assert nav.handled is True
    assert nav.text == "one"

    nav = history.previous("ignored")
    assert nav.handled is True
    assert nav.text is None  # already at oldest

    nav = history.next()
    assert nav.handled is True
    assert nav.text == "two"

    nav = history.next()
    assert nav.handled is True
    assert nav.text == "draft"

    nav = history.next()
    assert nav.handled is False

