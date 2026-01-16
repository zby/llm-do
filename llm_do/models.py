"""Model compatibility checking and resolution for workers."""
from __future__ import annotations

import fnmatch
import os
from typing import Any

from pydantic_ai.models import (
    Model,
    ModelMessage,
    ModelRequestParameters,
    ModelResponse,
)

LLM_DO_MODEL_ENV = "LLM_DO_MODEL"


class ModelError(ValueError):
    """Base class for model-related errors."""


class ModelCompatibilityError(ModelError):
    """Model is incompatible with worker requirements."""


class NoModelError(ModelError):
    """No model is available for a worker."""


class InvalidCompatibleModelsError(ModelError):
    """compatible_models configuration is invalid."""


class ModelConfigError(ModelError):
    """Model configuration is invalid."""


class NullModel(Model):
    """Model placeholder for tool-only contexts that should never invoke an LLM."""

    @property
    def model_name(self) -> str:
        return "null"

    @property
    def system(self) -> str:
        return "null"

    async def request(
        self, messages: list[ModelMessage], model_settings: Any, model_request_parameters: ModelRequestParameters
    ) -> ModelResponse:
        raise RuntimeError("NullModel cannot be used for LLM calls; configure a worker model instead.")


NULL_MODEL = NullModel()


def get_model_string(model: str | Model) -> str:
    """Get canonical string representation (provider:model_name)."""
    if isinstance(model, str):
        return model
    provider = type(model).__module__.split(".")[-1]
    return f"{provider}:{model.model_name}"


def model_matches_pattern(model: str, pattern: str) -> bool:
    """Check if model matches a glob-style compatibility pattern."""
    return fnmatch.fnmatch(model.strip().lower(), pattern.strip().lower())


def validate_model_compatibility(
    model: str | Model, compatible_models: list[str] | None, *, worker_name: str = "worker"
) -> None:
    """Validate model against compatibility patterns. Raises ModelCompatibilityError if invalid."""
    if compatible_models is None:
        return
    if not compatible_models:
        raise InvalidCompatibleModelsError(
            f"Worker '{worker_name}' has empty compatible_models list. Use ['*'] for any model."
        )
    model_str = get_model_string(model)
    if any(model_matches_pattern(model_str, p) for p in compatible_models):
        return
    patterns = ", ".join(f"'{p}'" for p in compatible_models)
    raise ModelCompatibilityError(f"Model '{model_str}' incompatible with '{worker_name}'. Patterns: {patterns}")


def get_env_model() -> str | None:
    """Get the default model from LLM_DO_MODEL environment variable."""
    return os.environ.get(LLM_DO_MODEL_ENV)


def select_model(
    *, worker_model: str | Model | None, compatible_models: list[str] | None, worker_name: str = "worker"
) -> str | Model:
    """Select and validate the effective model for a worker (worker_model > LLM_DO_MODEL env)."""
    if worker_model is not None and compatible_models is not None:
        raise ModelConfigError(f"Worker '{worker_name}' cannot have both 'model' and 'compatible_models' set.")
    if worker_model is not None:
        return worker_model
    env_model = os.environ.get(LLM_DO_MODEL_ENV)
    if env_model is not None:
        validate_model_compatibility(env_model, compatible_models, worker_name=worker_name)
        return env_model
    raise NoModelError(f"No model configured for worker '{worker_name}'. Set worker.model or {LLM_DO_MODEL_ENV}.")
