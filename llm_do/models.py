"""Model compatibility checking and resolution for workers."""
from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable
from typing import Any

from pydantic_ai.models import (
    Model,
    ModelMessage,
    ModelRequestParameters,
    ModelResponse,
    infer_model,
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

ModelFactory = Callable[[str], Model]
_MODEL_FACTORIES: dict[str, ModelFactory] = {}


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
    model: str | Model, compatible_models: list[str] | None, *, agent_name: str = "agent", worker_name: str | None = None
) -> None:
    """Validate model against compatibility patterns. Raises ModelCompatibilityError if invalid."""
    # Handle deprecated parameter
    if worker_name is not None:
        agent_name = worker_name
    if compatible_models is None:
        return
    if not compatible_models:
        raise InvalidCompatibleModelsError(
            f"Agent '{agent_name}' has empty compatible_models list. Use ['*'] for any model."
        )
    model_str = get_model_string(model)
    if any(model_matches_pattern(model_str, p) for p in compatible_models):
        return
    patterns = ", ".join(f"'{p}'" for p in compatible_models)
    raise ModelCompatibilityError(f"Model '{model_str}' incompatible with '{agent_name}'. Patterns: {patterns}")


def get_env_model() -> str | None:
    """Get the default model from LLM_DO_MODEL environment variable."""
    return os.environ.get(LLM_DO_MODEL_ENV)


def register_model_factory(provider: str, factory: ModelFactory, *, replace: bool = False) -> None:
    """Register a custom model factory for a provider prefix."""
    provider = provider.strip()
    if not provider:
        raise ValueError("Provider name must be non-empty.")
    if ":" in provider:
        raise ValueError("Provider name must not include ':'. Use the prefix only.")
    if provider in _MODEL_FACTORIES and not replace:
        raise ValueError(f"Model factory already registered for provider '{provider}'.")
    _MODEL_FACTORIES[provider] = factory


def resolve_model(model: str | Model) -> Model:
    """Resolve a model identifier into a Model instance, honoring custom factories."""
    if isinstance(model, Model):
        return model
    if not isinstance(model, str):
        raise TypeError("Model must be a string or Model instance.")
    if ":" in model:
        provider, model_name = model.split(":", 1)
        factory = _MODEL_FACTORIES.get(provider)
        if factory is not None:
            return factory(model_name)
    return infer_model(model)


def select_model(
    *, agent_model: str | Model | None = None, compatible_models: list[str] | None, agent_name: str = "agent",
    # Backwards compatibility aliases (deprecated)
    worker_model: str | Model | None = None, worker_name: str | None = None
) -> str | Model:
    """Select and validate the effective model for an agent (agent_model > LLM_DO_MODEL env)."""
    # Handle deprecated parameters
    if worker_model is not None:
        agent_model = worker_model
    if worker_name is not None:
        agent_name = worker_name

    if agent_model is not None and compatible_models is not None:
        raise ModelConfigError(f"Agent '{agent_name}' cannot have both 'model' and 'compatible_models' set.")
    if agent_model is not None:
        return agent_model
    env_model = os.environ.get(LLM_DO_MODEL_ENV)
    if env_model is not None:
        validate_model_compatibility(env_model, compatible_models, agent_name=agent_name)
        return env_model
    raise NoModelError(f"No model configured for agent '{agent_name}'. Set agent.model or {LLM_DO_MODEL_ENV}.")
