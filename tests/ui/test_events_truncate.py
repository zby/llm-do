from llm_do.ui.events import _truncate, _truncate_lines


def test_truncate_adds_ellipsis_when_long() -> None:
    assert _truncate("abcdef", 4) == "abcd..."


def test_truncate_lines_limits_lines() -> None:
    text = "a\nb\nc"
    assert _truncate_lines(text, 100, 2) == "a\nb\n... (1 more lines)"
