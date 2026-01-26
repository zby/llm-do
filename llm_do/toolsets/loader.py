"""Toolset resolution for agents."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from pydantic_ai.toolsets import AbstractToolset

ToolsetFactory = Callable[[], AbstractToolset[Any]]


@dataclass(frozen=True, slots=True)
class ToolsetSpec:
    """Specification for creating toolset instances."""

    factory: ToolsetFactory


def resolve_toolset_specs(
    toolsets_definition: Sequence[str],
    *,
    available_toolsets: Mapping[str, ToolsetSpec],
    agent_name: str = "",
    # Backwards compatibility alias (deprecated)
    worker_name: str | None = None,
) -> list[ToolsetSpec]:
    """Resolve toolset specs declared in an agent file.

    Toolsets are registered as factories (built-ins, Python toolsets, agents).
    Agent YAML may only reference toolset names.
    """
    # Handle deprecated parameter
    if worker_name is not None:
        agent_name = worker_name

    specs: list[ToolsetSpec] = []
    for toolset_name in toolsets_definition:
        spec = available_toolsets.get(toolset_name)
        if spec is None:
            available = sorted(available_toolsets.keys())
            raise ValueError(
                f"Unknown toolset {toolset_name!r} for agent {agent_name!r}. "
                f"Available: {available}"
            )
        specs.append(spec)
    return specs


def instantiate_toolsets(
    toolset_specs: Sequence[ToolsetSpec],
) -> list[AbstractToolset[Any]]:
    """Instantiate toolset specs for a specific call.
    """
    toolsets: list[AbstractToolset[Any]] = []
    for spec in toolset_specs:
        toolset = spec.factory()
        toolsets.append(toolset)
    return toolsets
