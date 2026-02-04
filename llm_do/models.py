"""Model compatibility checking and resolution for agents."""
from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

from pydantic_ai.exceptions import UserError
from pydantic_ai.models import (
    Model,
    ModelMessage,
    ModelRequestParameters,
    ModelResponse,
    infer_model,
)
from pydantic_ai.providers import infer_provider_class

LLM_DO_MODEL_ENV = "LLM_DO_MODEL"

ModelInput: TypeAlias = str | Model


class ModelError(ValueError):
    """Base class for model-related errors."""


class ModelCompatibilityError(ModelError):
    """Model is incompatible with agent requirements."""


class NoModelError(ModelError):
    """No model is available for an agent."""


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
        raise RuntimeError("NullModel cannot be used for LLM calls; configure an agent model instead.")


NULL_MODEL = NullModel()

ModelFactory = Callable[[str], Model]
_CUSTOM_MODEL_FACTORIES: dict[str, ModelFactory] = {}


@dataclass(frozen=True)
class ModelSelection:
    model: Model
    model_id: str | None


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
    model: str | Model, compatible_models: list[str] | None, *, agent_name: str = "agent"
) -> None:
    """Validate model against compatibility patterns. Raises ModelCompatibilityError if invalid."""
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


def _is_reserved_provider(provider: str) -> bool:
    if provider.startswith("gateway/"):
        return True
    try:
        infer_provider_class(provider)
    except ValueError:
        return False
    else:
        return True


def register_model_factory(provider: str, factory: ModelFactory, *, replace: bool = False) -> None:
    """Register a custom model factory for a provider prefix."""
    provider = provider.strip()
    if not provider:
        raise ValueError("Provider name must be non-empty.")
    if ":" in provider:
        raise ValueError("Provider name must not include ':'. Use the prefix only.")
    if _is_reserved_provider(provider):
        raise ValueError(
            f"Provider name '{provider}' is reserved by PydanticAI; choose a custom prefix instead."
        )
    if provider in _CUSTOM_MODEL_FACTORIES and not replace:
        raise ValueError(f"Model factory already registered for provider '{provider}'.")
    _CUSTOM_MODEL_FACTORIES[provider] = factory


def _resolve_model_string(model: str) -> Model:
    has_prefix = ":" in model
    if has_prefix:
        provider, model_name = model.split(":", 1)
        factory = _CUSTOM_MODEL_FACTORIES.get(provider)
        if factory is not None:
            return factory(model_name)
    try:
        return infer_model(model)
    except UserError as exc:
        if not has_prefix:
            raise ModelError(
                f"Unknown model '{model}'. Model identifiers must include a provider prefix, "
                "e.g. 'openai:gpt-4o-mini' or 'anthropic:claude-haiku-4-5'. "
                "If you are using a custom provider, register it with register_model_factory "
                "and use 'yourprefix:your-model'."
            ) from exc
        raise


def resolve_model_with_id(model: ModelInput) -> ModelSelection:
    """Resolve a model identifier into a Model instance and track its string id."""
    if isinstance(model, Model):
        return ModelSelection(model=model, model_id=None)
    if not isinstance(model, str):
        raise TypeError("Model must be a string or Model instance.")
    return ModelSelection(model=_resolve_model_string(model), model_id=model)


def resolve_model(model: ModelInput) -> Model:
    """Resolve a model identifier into a Model instance, honoring custom factories."""
    return resolve_model_with_id(model).model


def select_model_with_id(
    *, agent_model: str | Model | None = None, compatible_models: list[str] | None, agent_name: str = "agent"
) -> ModelSelection:
    """Select the effective model and return both Model and original identifier."""
    if agent_model is not None and compatible_models is not None:
        raise ModelConfigError(f"Agent '{agent_name}' cannot have both 'model' and 'compatible_models' set.")
    if agent_model is not None:
        return resolve_model_with_id(agent_model)
    env_model = get_env_model()
    if env_model is not None:
        validate_model_compatibility(env_model, compatible_models, agent_name=agent_name)
        return resolve_model_with_id(env_model)
    raise NoModelError(f"No model configured for agent '{agent_name}'. Set agent.model or {LLM_DO_MODEL_ENV}.")


def select_model(
    *, agent_model: str | Model | None = None, compatible_models: list[str] | None, agent_name: str = "agent"
) -> Model:
    """Select and validate the effective model for an agent (agent_model > LLM_DO_MODEL env)."""
    return select_model_with_id(
        agent_model=agent_model,
        compatible_models=compatible_models,
        agent_name=agent_name,
    ).model
