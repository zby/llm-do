"""Toolset resolution for workers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pydantic_ai.toolsets import AbstractToolset


@dataclass(frozen=True, slots=True)
class ToolsetBuildContext:
    """Dependencies and lookup tables for toolset resolution."""

    worker_name: str
    worker_path: Path | None = None
    available_toolsets: Mapping[str, AbstractToolset[Any]] = field(default_factory=dict)

    @property
    def worker_dir(self) -> Path | None:
        return self.worker_path.parent if self.worker_path else None


def build_toolsets(
    toolsets_definition: Mapping[str, Mapping[str, Any]],
    context: ToolsetBuildContext,
) -> list[AbstractToolset[Any]]:
    """Resolve toolset instances declared in a worker file.

    Toolsets are registered as instances (built-ins, Python toolsets, workers).
    Worker YAML may only reference toolset names; config is not allowed here.
    """
    toolsets: list[AbstractToolset[Any]] = []
    for toolset_name, toolset_config in toolsets_definition.items():
        if toolset_config:
            raise TypeError(
                f"Toolset {toolset_name!r} cannot be configured in worker YAML. "
                "Define a Python toolset instance with the desired config instead."
            )
        toolset = context.available_toolsets.get(toolset_name)
        if toolset is None:
            available = sorted(context.available_toolsets.keys())
            raise ValueError(
                f"Unknown toolset {toolset_name!r} for worker {context.worker_name!r}. "
                f"Available: {available}"
            )
        toolsets.append(toolset)
    return toolsets
