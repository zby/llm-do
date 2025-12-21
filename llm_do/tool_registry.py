"""Unified tool registry for code tools and workers."""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Optional

from .registry import WorkerRegistry


@dataclass(frozen=True)
class Tool:
    """Resolved tool reference."""

    name: str
    kind: Literal["code", "worker"]
    handler: Callable[..., Any] | str
    source_path: Path


class ToolRegistry:
    """Registry that resolves tools from tools.py and worker definitions."""

    def __init__(self, registry: WorkerRegistry):
        self._registry = registry
        self._tools_module = None
        self._code_tools: Optional[Dict[str, Callable[..., Any]]] = None
        self._tools_path: Optional[Path] = None

    @property
    def registry(self) -> WorkerRegistry:
        return self._registry

    def _find_tools_path(self) -> Optional[Path]:
        root_tools = self._registry.root / "tools.py"
        if root_tools.exists():
            return root_tools

        builtin_tools = Path(__file__).parent / "tools.py"
        if builtin_tools.exists():
            return builtin_tools

        return None

    def _load_tools_module(self, path: Path) -> Any:
        path_hash = hashlib.md5(str(path.resolve()).encode()).hexdigest()[:8]
        module_name = f"llm_do_tools_{path_hash}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load tools module at {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _discover_code_tools(self) -> Dict[str, Callable[..., Any]]:
        if self._code_tools is not None:
            return self._code_tools

        self._code_tools = {}
        self._tools_path = self._find_tools_path()
        if self._tools_path is None:
            return self._code_tools

        module = self._load_tools_module(self._tools_path)
        self._tools_module = module

        for name, obj in module.__dict__.items():
            if name.startswith("_"):
                continue
            if not (callable(obj) and inspect.isfunction(obj)):
                continue
            if obj.__module__ != module.__name__:
                continue
            self._code_tools[name] = obj

        return self._code_tools

    def _check_collisions(self) -> None:
        code_tools = set(self._discover_code_tools().keys())
        worker_names = set(self._registry.list_workers())
        collisions = sorted(code_tools & worker_names)
        if collisions:
            raise ValueError(
                "Ambiguous tools: "
                + ", ".join(
                    f"tools.py::{name} and {name}.worker" for name in collisions
                )
                + " both exist. Rename the tool(s) or worker(s) to remove ambiguity."
            )

    def resolve(self, name: str) -> Tool:
        """Resolve a tool name to a code tool or worker."""
        self._check_collisions()

        code_tools = self._discover_code_tools()
        if name in code_tools:
            tools_path = self._tools_path or self._find_tools_path()
            if tools_path is None:
                raise FileNotFoundError("tools.py not found for code tool resolution")
            return Tool(
                name=name,
                kind="code",
                handler=code_tools[name],
                source_path=tools_path,
            )

        worker_names = set(self._registry.list_workers())
        if name in worker_names:
            source_path = self._registry.resolve_worker_path(name)
            return Tool(
                name=name,
                kind="worker",
                handler=name,
                source_path=source_path,
            )

        raise FileNotFoundError(f"Tool not found: {name}")
