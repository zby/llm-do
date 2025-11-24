"""LangChain tool bridge for pydantic-ai workers."""
from __future__ import annotations

import importlib
from typing import Any, Iterable

from llm_do.pydanticai import WorkerContext


def _register_toolkit(agent: Any, toolkit: Any) -> None:
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
    raise TypeError("Unable to attach LangChain toolkit to pydantic-ai Agent")


def _load_toolkit(collection: str, tools: Iterable[str]):
    module = importlib.import_module("pydantic_ai.toolkits.langchain")
    factory = getattr(module, "langchain_toolkit", None) or getattr(module, "langchain_tools", None)
    if factory is None:
        raise ImportError(
            "LangChain toolkit factory not found. Upgrade pydantic-ai or adjust the helper."
        )
    return factory(tools=tools, collection=collection)


def register_tools(
    agent: Any,
    ctx: WorkerContext,
    *,
    collection: str = "community",
    tools: Iterable[str] = ("search", "wikipedia"),
) -> None:
    """Register LangChain tools shipped with pydantic-ai's integration."""

    try:
        toolkit = _load_toolkit(collection=collection, tools=tools)
    except ModuleNotFoundError as exc:
        raise ImportError(
            "Install pydantic-ai with LangChain support: pip install 'pydantic-ai[langchain]'"
        ) from exc

    _register_toolkit(agent, toolkit)
