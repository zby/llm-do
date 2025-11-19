"""llm plugin hooks for llm-do."""

from __future__ import annotations

import llm

from .tools_files import Files
from .tools_template_call import TemplateCall


@llm.hookimpl
def register_tools(register):
    """Expose the Files and TemplateCall toolboxes to llm."""
    register(Files)
    register(TemplateCall)
