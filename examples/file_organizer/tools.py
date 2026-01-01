"""File organization tools - deterministic filename sanitization.

This demonstrates the "hardening" pattern: the LLM decides what files should
be called (semantic decision), but the actual character sanitization is
handled by deterministic Python code (no LLM variability).
"""
import re

from pydantic_ai.toolsets import FunctionToolset

file_tools = FunctionToolset()


@file_tools.tool
def sanitize_filename(name: str) -> str:
    """Convert a human-readable filename to a clean, filesystem-safe format.

    Pass your SEMANTIC name with normal spacing and capitalization.
    Examples:
        "Meeting Notes.docx" → "meeting-notes.docx"
        "John's Report.pdf" → "johns-report.pdf"
        "Q1 Sales Data.xlsx" → "q1-sales-data.xlsx"

    Do NOT pre-sanitize - pass the readable name, I'll handle cleanup:
    - Converts to lowercase
    - Replaces spaces/underscores with hyphens
    - Removes special characters
    - Preserves file extension

    Args:
        name: Human-readable filename with extension (e.g. "My Report.pdf")

    Returns:
        Clean filename safe for any filesystem
    """
    # Split extension
    if "." in name:
        base, ext = name.rsplit(".", 1)
        ext = ext.lower()
    else:
        base, ext = name, ""

    # Lowercase
    base = base.lower()

    # Replace spaces and underscores with hyphens
    base = re.sub(r"[\s_]+", "-", base)

    # Remove special characters (keep alphanumeric and hyphens)
    base = re.sub(r"[^a-z0-9\-]", "", base)

    # Collapse multiple hyphens
    base = re.sub(r"-+", "-", base)

    # Strip leading/trailing hyphens
    base = base.strip("-")

    # Reassemble
    if ext:
        return f"{base}.{ext}"
    return base
