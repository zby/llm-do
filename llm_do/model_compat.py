"""Model compatibility checking and resolution for workers.

This module provides utilities for:
1. Validating model compatibility against worker's compatible_models patterns
2. Resolving the effective model from multiple sources with proper precedence

Pattern syntax for compatible_models:
- "*" matches any model
- "anthropic:*" matches any model from the anthropic provider
- "anthropic:claude-haiku-*" matches claude-haiku variants
- "anthropic:claude-haiku-4-5" matches exactly that model

Model resolution precedence (highest to lowest):
1. CLI --model flag (explicit override)
2. Worker's own model (worker definition)
3. Project config model (project.yaml)
4. LLM_DO_MODEL environment variable
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from typing import Any, List, Optional

# Environment variable for default model
LLM_DO_MODEL_ENV = "LLM_DO_MODEL"


class ModelCompatibilityError(ValueError):
    """Raised when a model is incompatible with worker requirements."""
    pass


class NoModelError(ValueError):
    """Raised when no model is available for a worker."""
    pass


class InvalidCompatibleModelsError(ValueError):
    """Raised when compatible_models configuration is invalid (e.g., empty list)."""
    pass


@dataclass
class ModelValidationResult:
    """Result of model compatibility validation."""

    valid: bool
    model: str
    message: Optional[str] = None


def _normalize_pattern(pattern: str) -> str:
    """Normalize a pattern for matching."""
    return pattern.strip().lower()


def _normalize_model(model: str) -> str:
    """Normalize a model identifier for matching."""
    return model.strip().lower()


def model_matches_pattern(model: str, pattern: str) -> bool:
    """Check if a model matches a compatibility pattern.

    Uses fnmatch for glob-style matching:
    - "*" matches everything
    - "anthropic:*" matches "anthropic:claude-sonnet-4"
    - "anthropic:claude-*" matches "anthropic:claude-sonnet-4", "anthropic:claude-haiku-4-5"

    Args:
        model: The model identifier to check (e.g., "anthropic:claude-sonnet-4")
        pattern: The pattern to match against (e.g., "anthropic:*")

    Returns:
        True if the model matches the pattern
    """
    normalized_model = _normalize_model(model)
    normalized_pattern = _normalize_pattern(pattern)
    return fnmatch.fnmatch(normalized_model, normalized_pattern)


def validate_model_compatibility(
    model: str,
    compatible_models: Optional[List[str]],
    *,
    worker_name: str = "worker",
) -> ModelValidationResult:
    """Validate that a model is compatible with the worker's requirements.

    Compatibility rules:
    - None (unset): Any model is allowed
    - ["*"]: Explicitly allows any model
    - []: Empty list is invalid (configuration error)
    - ["pattern1", "pattern2", ...]: Model must match at least one pattern

    Args:
        model: The model identifier to validate
        compatible_models: List of compatibility patterns from worker definition
        worker_name: Name of the worker (for error messages)

    Returns:
        ModelValidationResult indicating if the model is valid

    Raises:
        ValueError: If compatible_models is an empty list (invalid configuration)
    """
    # None means any model is allowed
    if compatible_models is None:
        return ModelValidationResult(valid=True, model=model)

    # Empty list is a configuration error
    if len(compatible_models) == 0:
        raise InvalidCompatibleModelsError(
            f"Worker '{worker_name}' has empty compatible_models list. "
            "Use ['*'] for any model, or specify compatible patterns."
        )

    # Check if model matches any pattern
    for pattern in compatible_models:
        if model_matches_pattern(model, pattern):
            return ModelValidationResult(valid=True, model=model)

    # No match found
    patterns_display = ", ".join(f"'{p}'" for p in compatible_models)
    return ModelValidationResult(
        valid=False,
        model=model,
        message=(
            f"Model '{model}' is not compatible with worker '{worker_name}'. "
            f"Compatible patterns: {patterns_display}"
        ),
    )


def _validate_and_return(
    model: Any,
    compatible_models: Optional[List[str]],
    worker_name: str,
) -> Any:
    """Validate a model against compatibility patterns and return it.

    Only validates string model identifiers; Model objects are used as-is.

    Raises:
        ModelCompatibilityError: If the model doesn't match compatible_models
    """
    if isinstance(model, str):
        result = validate_model_compatibility(
            model, compatible_models, worker_name=worker_name
        )
        if not result.valid:
            raise ModelCompatibilityError(result.message)
    return model


def get_env_model() -> Optional[str]:
    """Get the default model from LLM_DO_MODEL environment variable."""
    return os.environ.get(LLM_DO_MODEL_ENV)


def select_model(
    *,
    worker_model: Optional[str],
    cli_model: Optional[str] = None,
    project_model: Optional[str] = None,
    compatible_models: Optional[List[str]],
    worker_name: str = "worker",
) -> str:
    """Select and validate the effective model for a worker.

    Resolution order (highest to lowest priority):
    1. CLI --model flag - explicit user override
    2. Worker's own model - worker definition
    3. Project config model - project-wide default
    4. LLM_DO_MODEL env var - user's global default

    The selected model is validated against compatible_models.

    Args:
        worker_model: Model from worker definition
        cli_model: Model from --model CLI flag
        project_model: Model from project.yaml config
        compatible_models: Worker's compatibility patterns
        worker_name: Name of the worker (for error messages)

    Returns:
        The selected model identifier

    Raises:
        ModelCompatibilityError: If selected model is incompatible with worker
        NoModelError: If no model is available from any source
    """
    # 1. CLI model - explicit user override (highest priority)
    if cli_model is not None:
        return _validate_and_return(cli_model, compatible_models, worker_name)

    # 2. Worker's own model
    if worker_model is not None:
        return _validate_and_return(worker_model, compatible_models, worker_name)

    # 3. Project config model - project-wide default
    if project_model is not None:
        return _validate_and_return(project_model, compatible_models, worker_name)

    # 4. Environment variable - user's global default
    env_model = get_env_model()
    if env_model is not None:
        return _validate_and_return(env_model, compatible_models, worker_name)

    # No model available
    raise NoModelError(
        f"No model configured for worker '{worker_name}'. "
        f"Set worker.model, project.yaml model, --model flag, or {LLM_DO_MODEL_ENV} env var."
    )
