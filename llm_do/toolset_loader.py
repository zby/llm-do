"""Dynamic toolset loading for llm-do workers.

This module provides factory functions to dynamically load and instantiate
toolsets based on class paths specified in worker configuration.

All toolsets receive `config` in their constructor. Runtime dependencies
(worker context) are accessed via ctx.deps in get_tools/call_tool.
"""
from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_blocking_approval import ApprovalMemory, ApprovalToolset

if TYPE_CHECKING:
    from .types import WorkerContext

logger = logging.getLogger(__name__)

# Aliases for built-in toolsets
ALIASES: Dict[str, str] = {
    "shell": "llm_do.shell.toolset.ShellToolset",
    "delegation": "llm_do.delegation_toolset.DelegationToolset",
    "filesystem": "llm_do.filesystem_toolset.FileSystemToolset",
    "custom": "llm_do.custom_toolset.CustomToolset",
}


def _normalize_custom_tool_config(value: Any) -> Dict[str, Any]:
    """Normalize custom tool config to an approval config dict."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, bool):
        return {"pre_approved": value}
    return {}


def _build_custom_approval_config(
    tool_config: Dict[str, Any],
    approval_overrides: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Build approval config from allowed custom tools, with optional overrides."""
    merged: Dict[str, Dict[str, Any]] = {}
    for name, config in tool_config.items():
        merged[name] = _normalize_custom_tool_config(config)

    for name, config in approval_overrides.items():
        if name in merged:
            merged[name] = _normalize_custom_tool_config(config)

    return merged


def _resolve_class_path(class_path: str) -> str:
    """Resolve alias to full class path if applicable."""
    return ALIASES.get(class_path, class_path)


def _import_class(class_path: str) -> type:
    """Dynamically import a class from its fully-qualified path.

    Args:
        class_path: Fully qualified class path, e.g., 'llm_do.shell.toolset.ShellToolset'

    Returns:
        The imported class

    Raises:
        ImportError: If the module cannot be imported
        AttributeError: If the class doesn't exist in the module
    """
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def create_toolset(
    class_path: str,
    config: Dict[str, Any],
    context: "WorkerContext",
    approval_callback: Callable,
    memory: ApprovalMemory,
) -> AbstractToolset:
    """Factory to create a single toolset from config.

    All toolsets receive `config` and access runtime deps via ctx.deps.

    Args:
        class_path: Fully qualified class path or alias
        config: Toolset configuration dict
        context: Worker execution context with runtime deps
        approval_callback: Callback for approval requests
        memory: Approval memory for tracking decisions

    Returns:
        Wrapped toolset with ApprovalToolset
    """
    # Resolve alias
    resolved_path = _resolve_class_path(class_path)

    # Import the class
    toolset_class = _import_class(resolved_path)

    # Copy config to avoid mutation
    config = dict(config)

    # Extract approval config (for toolsets without needs_approval)
    approval_config = config.pop("_approval_config", {})

    # Custom toolset uses tool config for approvals (per-tool pre_approved)
    from .custom_toolset import CustomToolset

    if issubclass(toolset_class, CustomToolset):
        approval_config = _build_custom_approval_config(config, approval_config)

    # All toolsets receive config, access ctx.deps at runtime
    toolset = toolset_class(config=config)

    logger.debug("Created toolset %s", resolved_path)

    # Wrap with ApprovalToolset - it auto-detects needs_approval
    return ApprovalToolset(
        inner=toolset,
        approval_callback=approval_callback,
        memory=memory,
        config=approval_config,
    )


def build_toolsets(
    toolsets_config: Dict[str, Any],
    context: "WorkerContext",
) -> List[AbstractToolset]:
    """Build all toolsets from worker definition.

    Args:
        toolsets_config: Dict mapping class paths (or aliases) to config dicts
        context: Worker execution context

    Returns:
        List of wrapped toolsets ready for worker execution
    """
    toolsets = []

    for class_path, toolset_config in toolsets_config.items():
        # Handle None config (just enable with defaults)
        if toolset_config is None:
            toolset_config = {}

        toolset = create_toolset(
            class_path=class_path,
            config=toolset_config,
            context=context,
            approval_callback=context.approval_controller.approval_callback,
            memory=context.approval_controller.memory,
        )
        toolsets.append(toolset)

    return toolsets
