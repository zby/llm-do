"""Helpers for coercing worker inputs."""
from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel


def schema_accepts_input_field(schema_in: Type[BaseModel] | None) -> bool:
    """Return True if the schema accepts an `input` field (or is unset)."""
    if schema_in is None:
        return True

    fields = getattr(schema_in, "model_fields", {}) or {}
    if "input" in fields:
        return True

    for field in fields.values():
        alias = getattr(field, "alias", None)
        if alias == "input":
            return True
        validation_alias = getattr(field, "validation_alias", None)
        if validation_alias == "input":
            return True

    return False


def coerce_worker_input(schema_in: Type[BaseModel] | None, input_data: Any) -> Any:
    """Coerce plain text into {'input': text} when the schema allows it."""
    if isinstance(input_data, BaseModel):
        return input_data.model_dump()

    if isinstance(input_data, str) and schema_accepts_input_field(schema_in):
        return {"input": input_data}

    return input_data
