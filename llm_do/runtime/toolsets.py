"""Toolset lifecycle helpers for runtime call scopes."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)


async def cleanup_toolsets(toolsets: Sequence[Any]) -> None:
    """Run cleanup hooks on toolset instances, logging failures."""
    for toolset in toolsets:
        cleanup = getattr(toolset, "cleanup", None)
        if cleanup is None:
            continue
        try:
            result = cleanup()
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("Toolset cleanup failed for %r", toolset)
