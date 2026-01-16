from llm_do.ui.formatting import truncate_lines, truncate_text


def test_truncate_adds_suffix_when_long() -> None:
    assert truncate_text("abcdef", 4) == "abcd... [truncated]"


def test_truncate_lines_limits_lines() -> None:
    text = "a\nb\nc"
    assert truncate_lines(text, 100, 2) == "a\nb\n... (1 more lines)"
