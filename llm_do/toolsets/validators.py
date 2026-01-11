"""Validation helpers for toolset argument schemas."""
from __future__ import annotations

from typing import Any, Literal, Type

from pydantic import BaseModel, TypeAdapter


class DictValidator:
    """Validator wrapper that validates against a schema but returns dicts."""

    def __init__(self, schema: Type[BaseModel]) -> None:
        self._adapter = TypeAdapter(schema)
        self._inner = self._adapter.validator

    def _to_dict(self, result: Any) -> dict[str, Any]:
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result

    def validate_python(
        self,
        input: Any,
        *,
        allow_partial: bool | Literal["off", "on", "trailing-strings"] = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = self._inner.validate_python(input, allow_partial=allow_partial, **kwargs)
        return self._to_dict(result)

    def validate_json(
        self,
        input: str | bytes | bytearray,
        *,
        allow_partial: bool | Literal["off", "on", "trailing-strings"] = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = self._inner.validate_json(input, allow_partial=allow_partial, **kwargs)
        return self._to_dict(result)

    def validate_strings(self, data: Any, **kwargs: Any) -> dict[str, Any]:
        result = self._inner.validate_strings(data, **kwargs)
        return self._to_dict(result)
