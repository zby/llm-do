"""Template-first workflows for the llm CLI."""

from __future__ import annotations

__all__ = ["__version__", "Files", "TemplateCall"]

__version__ = "0.2.0"

from .tools_files import Files
from .tools_template_call import TemplateCall
