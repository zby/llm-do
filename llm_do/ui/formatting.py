"""Shared formatting helpers for UI output."""
from __future__ import annotations

TRUNCATION_SUFFIX = "... [truncated]"
LINES_TRUNCATION_SUFFIX = "... ({count} more lines)"


def truncate_text(text: str, max_len: int, *, suffix: str = TRUNCATION_SUFFIX) -> str:
    """Truncate text to max_len, appending a suffix when truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + suffix


def truncate_lines(
    text: str,
    max_len: int,
    max_lines: int,
    *,
    suffix: str = TRUNCATION_SUFFIX,
    lines_suffix: str = LINES_TRUNCATION_SUFFIX,
) -> str:
    """Truncate text by length and line count."""
    text = truncate_text(text, max_len, suffix=suffix)
    lines = text.split("\n")
    if len(lines) > max_lines:
        extra = len(lines) - max_lines
        return "\n".join(lines[:max_lines]) + f"\n{lines_suffix.format(count=extra)}"
    return text
