"""Shared context-injection helpers for tools."""
from __future__ import annotations

from typing import Callable, Optional

_CONTEXT_ATTR = "_llm_do_context"
_CONTEXT_PARAM_ATTR = "_llm_do_context_param"


def tool_context(func: Optional[Callable] = None, *, param: str = "ctx") -> Callable:
    """Mark a tool as context-aware.

    The context is injected under the parameter name given by ``param`` and is
    excluded from any LLM-facing JSON schema in custom toolsets.
    """

    def _decorate(target: Callable) -> Callable:
        setattr(target, _CONTEXT_ATTR, True)
        setattr(target, _CONTEXT_PARAM_ATTR, param)
        return target

    if func is None:
        return _decorate
    return _decorate(func)


def get_context_param(func: Callable) -> Optional[str]:
    """Return the injected context parameter name if configured."""
    if getattr(func, _CONTEXT_ATTR, False):
        return getattr(func, _CONTEXT_PARAM_ATTR, "ctx")
    return None
