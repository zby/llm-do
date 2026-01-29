"""Tests for custom model factory registration."""
import pytest
from pydantic_ai.models.test import TestModel

from llm_do.models import register_model_factory, resolve_model


def test_register_model_factory_resolves_custom_model() -> None:
    seen: dict[str, str] = {}

    def factory(model_name: str) -> TestModel:
        seen["model_name"] = model_name
        return TestModel(custom_output_text="ok")

    register_model_factory("custom_provider_test", factory)

    model = resolve_model("custom_provider_test:demo")
    assert isinstance(model, TestModel)
    assert seen["model_name"] == "demo"


def test_register_model_factory_duplicate_raises() -> None:
    def factory(model_name: str) -> TestModel:
        return TestModel(custom_output_text=model_name)

    register_model_factory("custom_provider_dup_test", factory)

    with pytest.raises(ValueError, match="already registered"):
        register_model_factory("custom_provider_dup_test", factory)
