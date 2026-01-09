"""Approval config helpers for toolset instances."""
from __future__ import annotations

from typing import Any

from pydantic_ai.toolsets import AbstractToolset

TOOLSET_APPROVAL_ATTR = "__llm_do_approval_config__"


def get_toolset_approval_config(
    toolset: AbstractToolset[Any],
) -> dict[str, dict[str, Any]] | None:
    """Return per-tool approval config stored on a toolset instance."""
    config = getattr(toolset, TOOLSET_APPROVAL_ATTR, None)
    if config is None:
        return None
    if not isinstance(config, dict):
        raise TypeError(
            f"{TOOLSET_APPROVAL_ATTR} must be a dict; got {type(config)} for {toolset}"
        )
    return config


def set_toolset_approval_config(
    toolset: AbstractToolset[Any],
    config: dict[str, dict[str, Any]],
) -> AbstractToolset[Any]:
    """Attach per-tool approval config to a toolset instance."""
    setattr(toolset, TOOLSET_APPROVAL_ATTR, config)
    return toolset
