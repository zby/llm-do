"""Resolve input model references for agent files."""
from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

from pydantic import BaseModel

from .discovery import load_module
from .path_refs import is_path_ref, resolve_path_ref, split_ref


def _split_input_model_ref(model_ref: str) -> tuple[str, str]:
    if ":" in model_ref:
        module_ref, class_name = split_ref(
            model_ref,
            delimiter=":",
            error_message="input_model_ref must use 'module.Class' or 'path.py:Class' syntax",
        )
    else:
        if "." not in model_ref:
            raise ValueError(
                "input_model_ref must use 'module.Class' or 'path.py:Class' syntax"
            )
        module_ref, class_name = split_ref(
            model_ref,
            delimiter=".",
            error_message="input_model_ref must use 'module.Class' or 'path.py:Class' syntax",
        )

    return module_ref, class_name


def _load_model_module(module_ref: str, base_path: Path | None) -> ModuleType:
    if is_path_ref(module_ref):
        path = resolve_path_ref(
            module_ref,
            base_path=base_path,
            error_message="input_model_ref uses a relative path but no base path was provided",
        )
        return load_module(path)

    return importlib.import_module(module_ref)


def resolve_input_model_ref(
    model_ref: str, base_path: Path | None = None
) -> type[BaseModel]:
    """Resolve input model ref to a Pydantic BaseModel subclass."""
    module_ref, class_name = _split_input_model_ref(model_ref)
    module = _load_model_module(module_ref, base_path)
    value = getattr(module, class_name, None)
    if value is None:
        raise ValueError(f"Input model {class_name!r} not found in {module_ref!r}")
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        raise TypeError(f"{model_ref!r} did not resolve to a BaseModel subclass")
    return value
