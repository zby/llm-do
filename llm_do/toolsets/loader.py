"""Toolset resolution for workers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from pydantic_ai.toolsets import AbstractToolset

ToolsetFactory = Callable[["ToolsetBuildContext"], AbstractToolset[Any]]


@dataclass(frozen=True, slots=True)
class ToolsetSpec:
    """Specification for creating toolset instances."""

    factory: ToolsetFactory


@dataclass(frozen=True, slots=True)
class ToolsetBuildContext:
    """Dependencies and lookup tables for toolset resolution."""

    worker_name: str
    available_toolsets: Mapping[str, ToolsetSpec] = field(default_factory=dict)


def _wrap_entry_as_toolset(toolset: Any) -> AbstractToolset[Any]:
    """Wrap an AgentEntry in EntryToolset if needed."""
    # Import here to avoid circular imports
    from ..runtime.entries import AgentEntry, EntryToolset

    if isinstance(toolset, AgentEntry):
        return EntryToolset(entry=toolset)
    return toolset


def resolve_toolset_specs(
    toolsets_definition: Sequence[str],
    context: ToolsetBuildContext,
) -> list[ToolsetSpec]:
    """Resolve toolset specs declared in a worker file.

    Toolsets are registered as factories (built-ins, Python toolsets, workers).
    Worker YAML may only reference toolset names.
    """
    specs: list[ToolsetSpec] = []
    for toolset_name in toolsets_definition:
        spec = context.available_toolsets.get(toolset_name)
        if spec is None:
            available = sorted(context.available_toolsets.keys())
            raise ValueError(
                f"Unknown toolset {toolset_name!r} for worker {context.worker_name!r}. "
                f"Available: {available}"
            )
        specs.append(spec)
    return specs


def instantiate_toolsets(
    toolset_specs: Sequence[ToolsetSpec],
    context: ToolsetBuildContext,
) -> list[AbstractToolset[Any]]:
    """Instantiate toolset specs for a specific call.

    AgentEntry instances are automatically wrapped in EntryToolset adapters.
    """
    toolsets: list[AbstractToolset[Any]] = []
    for spec in toolset_specs:
        toolset = spec.factory(context)
        toolsets.append(_wrap_entry_as_toolset(toolset))
    return toolsets
