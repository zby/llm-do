"""CLI configuration override utilities.

This module provides functionality for overriding worker configuration at runtime
via the --set CLI flag without modifying YAML files.

Phase 1 (MVP): Simple --set overrides with dot notation and basic type inference.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .types import WorkerDefinition


def parse_set_override(spec: str) -> tuple[str, Any]:
    """Parse --set KEY=VALUE specification.

    Args:
        spec: Override specification in format KEY=VALUE

    Returns:
        Tuple of (key_path, value) where key_path supports dot notation

    Raises:
        ValueError: If spec format is invalid

    Examples:
        >>> parse_set_override("model=gpt-4")
        ('model', 'gpt-4')
        >>> parse_set_override("attachment_policy.max_attachments=10")
        ('attachment_policy.max_attachments', 10)
        >>> parse_set_override("toolsets.shell.rules=[{\"pattern\":\"git\"}]")
        ('toolsets.shell.rules', [{'pattern': 'git'}])
    """
    if '=' not in spec:
        raise ValueError(
            f"Invalid --set format: {spec!r}. Expected KEY=VALUE "
            f"(e.g., --set model=openai:gpt-4o)"
        )

    key, value_str = spec.split('=', 1)
    key = key.strip()
    value = _parse_value(value_str.strip())

    if not key:
        raise ValueError(f"Empty key in --set: {spec!r}")

    return (key, value)


def _parse_value(value_str: str) -> Any:
    """Parse value string with type inference.

    Attempts to parse in this order:
    1. JSON (for lists, dicts, null, and JSON literals)
    2. Boolean literals (true/false, case-insensitive)
    3. Numbers (int, float)
    4. Strings (default)

    Args:
        value_str: String representation of the value

    Returns:
        Parsed value with appropriate Python type

    Examples:
        >>> _parse_value("true")
        True
        >>> _parse_value("42")
        42
        >>> _parse_value("3.14")
        3.14
        >>> _parse_value('["a", "b"]')
        ['a', 'b']
        >>> _parse_value("hello")
        'hello'
    """
    if not value_str:
        return ""

    # Try JSON first (handles lists, dicts, null, numbers, booleans as JSON literals)
    try:
        return json.loads(value_str)
    except (json.JSONDecodeError, ValueError):
        pass

    # Boolean literals (case-insensitive)
    lower = value_str.lower()
    if lower in ('true', 'yes', 'on'):
        return True
    if lower in ('false', 'no', 'off'):
        return False

    # Try parsing as number
    try:
        # Check for decimal point to distinguish int from float
        if '.' in value_str or 'e' in value_str.lower():
            return float(value_str)
        return int(value_str)
    except ValueError:
        pass

    # Default: treat as string
    return value_str


def apply_set_override(data: Dict[str, Any], key_path: str, value: Any) -> None:
    """Apply a single --set override to the worker definition data.

    Uses dot notation to navigate nested fields. Creates intermediate
    dictionaries as needed.

    Args:
        data: Worker definition as dict (modified in place)
        key_path: Dot-separated path (e.g., 'toolsets.shell.rules')
        value: Parsed value to set

    Raises:
        ValueError: If path navigation fails (non-dict encountered)

    Examples:
        >>> data = {"model": "old"}
        >>> apply_set_override(data, "model", "new")
        >>> data
        {'model': 'new'}

        >>> data = {}
        >>> apply_set_override(data, "attachment_policy.max_attachments", 10)
        >>> data
        {'attachment_policy': {'max_attachments': 10}}
    """
    keys = key_path.split('.')
    target = data

    # Navigate to the parent of the target field, creating dicts as needed
    for key in keys[:-1]:
        if key not in target or target[key] is None:
            target[key] = {}
        elif not isinstance(target[key], dict):
            raise ValueError(
                f"Cannot navigate through non-dict field '{key}' in path '{key_path}'. "
                f"Field is type {type(target[key]).__name__}"
            )
        target = target[key]

    # Set the final value
    final_key = keys[-1]
    target[final_key] = value


def apply_cli_overrides(
    definition: WorkerDefinition,
    *,
    set_overrides: List[str],
) -> WorkerDefinition:
    """Apply CLI --set overrides to a worker definition.

    Args:
        definition: Original worker definition from YAML
        set_overrides: List of --set KEY=VALUE specifications

    Returns:
        New WorkerDefinition with overrides applied and validated

    Raises:
        ValueError: If overrides are invalid or result in invalid config

    Example:
        >>> from llm_do import WorkerDefinition
        >>> defn = WorkerDefinition(name="test", instructions="test")
        >>> overridden = apply_cli_overrides(
        ...     defn,
        ...     set_overrides=["model=openai:gpt-4o", "locked=true"]
        ... )
        >>> overridden.model
        'openai:gpt-4o'
        >>> overridden.locked
        True
    """
    if not set_overrides:
        return definition

    # Convert to dict for manipulation
    # Use exclude_unset=False to include all fields (even defaults)
    data = definition.model_dump(mode='python', exclude_unset=False)

    # Apply each --set override in order (last wins for conflicts)
    for set_spec in set_overrides:
        try:
            key_path, value = parse_set_override(set_spec)
            apply_set_override(data, key_path, value)
        except ValueError as e:
            raise ValueError(f"Invalid --set override {set_spec!r}: {e}")

    # Validate by reconstructing WorkerDefinition
    # This ensures overrides don't violate the schema
    try:
        return WorkerDefinition.model_validate(data)
    except Exception as e:
        raise ValueError(
            f"Overrides resulted in invalid worker configuration: {e}\n"
            f"Applied overrides: {set_overrides}"
        )
