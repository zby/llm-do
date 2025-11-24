"""ACI.dev tool wiring for pydantic-ai workers.

This module keeps the integration alongside the worker definition so prompts
and tooling move together. The loader calls ``register_tools`` with the active
agent and ``WorkerContext``. The function tries a few known integration shapes
from ``pydantic-ai`` and provides clear errors if the optional extra isn't
installed.
"""
from __future__ import annotations

import importlib
from typing import Any

from llm_do.pydanticai import WorkerContext


def _register_toolkit(agent: Any, toolkit: Any) -> None:
    """Best-effort registration across pydantic-ai toolkit APIs."""

    if hasattr(toolkit, "register_tools"):
        toolkit.register_tools(agent)
        return
    if hasattr(toolkit, "register"):
        toolkit.register(agent)
        return
    if hasattr(agent, "toolkit"):
        agent.toolkit(toolkit)
        return
    if hasattr(agent, "add_toolkit"):
        agent.add_toolkit(toolkit)
        return
    raise TypeError(
        "Unable to attach ACI.dev toolkit. Update the helper to match the "
        "pydantic-ai release you are using."
    )


def register_tools(
    agent: Any,
    ctx: WorkerContext,
    *,
    api_key_env: str = "ACI_API_KEY",
    base_url: str = "https://api.aci.dev",
) -> None:
    """Register ACI.dev tools using the pydantic-ai integration if available."""

    try:
        toolkit_module = importlib.import_module("pydantic_ai.toolkits.aci")
    except ModuleNotFoundError as exc:
        raise ImportError(
            "Install pydantic-ai with the ACI extra: pip install 'pydantic-ai[aci]'"
        ) from exc

    for candidate in ("aci_toolkit", "aci_tools", "AciToolkit"):
        factory = getattr(toolkit_module, candidate, None)
        if factory is None:
            continue
        toolkit = factory(api_key_env=api_key_env, base_url=base_url)
        _register_toolkit(agent, toolkit)
        return

    raise ImportError(
        "pydantic-ai ACI integration not found. Check the integration name for your version."
    )
