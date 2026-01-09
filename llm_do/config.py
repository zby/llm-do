"""CLI configuration override utilities.

This module provides functionality for overriding worker configuration at runtime
via the --set CLI flag without modifying YAML files.

Works with raw dictionaries, so it can be applied before parsing into typed objects.
"""
from __future__ import annotations

import json
from typing import Any


def parse_set_override(spec: str) -> tuple[str, Any]:
    """Parse --set KEY=VALUE specification.

    Args:
        spec: Override specification in format KEY=VALUE

    Returns:
        Tuple of (key_path, value) where key_path supports dot notation and
        bracketed literal keys (e.g., data["key.with.dots"]).

    Raises:
        ValueError: If spec format is invalid

    Examples:
        >>> parse_set_override("model=gpt-4")
        ('model', 'gpt-4')
        >>> parse_set_override("server_side_tools=[{\"tool_type\":\"web_search\"}]")
        ('server_side_tools', [{'tool_type': 'web_search'}])
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
        >>> _parse_value('["a", "b"]')
        ['a', 'b']
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
        if '.' in value_str or 'e' in value_str.lower():
            return float(value_str)
        return int(value_str)
    except ValueError:
        pass

    # Default: treat as string
    return value_str


def _parse_key_path(key_path: str) -> list[str]:
    """Parse a key path with dot notation and bracketed literal keys."""
    keys: list[str] = []
    buf: list[str] = []
    i = 0
    last_was_bracket = False

    while i < len(key_path):
        ch = key_path[i]
        if ch == ".":
            if last_was_bracket and not buf:
                last_was_bracket = False
                i += 1
                continue
            keys.append("".join(buf))
            buf = []
            last_was_bracket = False
            i += 1
            continue

        if ch == "[":
            if buf:
                keys.append("".join(buf))
                buf = []
            i += 1
            if i >= len(key_path) or key_path[i] not in ("'", '"'):
                raise ValueError(
                    f"Invalid bracket syntax in key path {key_path!r}: expected quoted key"
                )
            quote = key_path[i]
            i += 1
            literal: list[str] = []
            while i < len(key_path):
                ch = key_path[i]
                if ch == "\\":
                    if i + 1 >= len(key_path):
                        raise ValueError(
                            f"Invalid escape in bracketed key path {key_path!r}"
                        )
                    literal.append(key_path[i + 1])
                    i += 2
                    continue
                if ch == quote:
                    i += 1
                    break
                literal.append(ch)
                i += 1
            else:
                raise ValueError(
                    f"Unterminated quoted key in key path {key_path!r}"
                )
            if i >= len(key_path) or key_path[i] != "]":
                raise ValueError(
                    f"Invalid bracket syntax in key path {key_path!r}: missing ']'"
                )
            i += 1
            keys.append("".join(literal))
            last_was_bracket = True
            continue

        buf.append(ch)
        last_was_bracket = False
        i += 1

    if buf or not last_was_bracket:
        keys.append("".join(buf))

    return keys


def apply_set_override(data: dict[str, Any], key_path: str, value: Any) -> None:
    """Apply a single --set override to a dictionary.

    Uses dot notation to navigate nested fields. Supports bracketed
    literal keys for entries that contain dots. Creates intermediate
    dictionaries as needed.

    Args:
        data: Dictionary to modify (modified in place)
        key_path: Dot-separated path (e.g., 'server_side_tools.0.tool_type') or
            bracketed literal key (e.g., 'data["key.with.dots"]')
        value: Parsed value to set

    Raises:
        ValueError: If path navigation fails (non-dict encountered)

    Examples:
        >>> data = {"model": "old"}
        >>> apply_set_override(data, "model", "new")
        >>> data
        {'model': 'new'}

        >>> data = {}
        >>> apply_set_override(data, "server_side_tools", [{"tool_type": "web_search"}])
        >>> data
        {'server_side_tools': [{'tool_type': 'web_search'}]}
    """
    keys = _parse_key_path(key_path)
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


def apply_overrides(data: dict[str, Any], set_overrides: list[str]) -> dict[str, Any]:
    """Apply multiple --set overrides to a dictionary.

    Args:
        data: Dictionary to modify (a copy is made)
        set_overrides: List of --set KEY=VALUE specifications

    Returns:
        New dictionary with overrides applied

    Raises:
        ValueError: If any override is invalid

    Example:
        >>> data = {"model": "old", "name": "test"}
        >>> result = apply_overrides(data, ["model=new", "server_side_tools=[{\"tool_type\":\"web_search\"}]"])
        >>> result["model"]
        'new'
        >>> result["server_side_tools"][0]["tool_type"]
        'web_search'
    """
    if not set_overrides:
        return data

    # Make a shallow copy to avoid modifying the original
    result = dict(data)

    for set_spec in set_overrides:
        try:
            key_path, value = parse_set_override(set_spec)
            apply_set_override(result, key_path, value)
        except ValueError as e:
            raise ValueError(f"Invalid --set override {set_spec!r}: {e}")

    return result
