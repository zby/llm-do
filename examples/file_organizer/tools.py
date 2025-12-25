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
    """Sanitize a filename to a clean, consistent format.

    This is the "hardened" part - deterministic, tested, no LLM variability.
    The LLM decides what the file should be called; this function ensures
    the name is filesystem-safe and follows conventions.

    Transformations:
    - Converts to lowercase
    - Replaces spaces and underscores with hyphens
    - Removes special characters except hyphens, dots, and alphanumerics
    - Collapses multiple hyphens into one
    - Preserves file extension

    Args:
        name: The proposed filename (can include extension)

    Returns:
        Sanitized filename safe for any filesystem
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
