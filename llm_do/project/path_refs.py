"""Shared helpers for resolving path-based references."""
from __future__ import annotations

from pathlib import Path


def split_ref(value: str, *, delimiter: str, error_message: str) -> tuple[str, str]:
    """Split a ref string on a delimiter, enforcing both sides."""
    if delimiter not in value:
        raise ValueError(error_message)
    module_ref, name = value.rsplit(delimiter, 1)
    module_ref = module_ref.strip()
    name = name.strip()
    if not module_ref or not name:
        raise ValueError(error_message)
    return module_ref, name


def is_path_ref(module_ref: str) -> bool:
    """Return True if the ref looks like a filesystem path."""
    return (
        module_ref.endswith(".py")
        or "/" in module_ref
        or "\\" in module_ref
        or module_ref.startswith((".", "~"))
    )


def resolve_path_ref(
    path_ref: str,
    *,
    base_path: Path | None,
    error_message: str | None = None,
    allow_cwd_fallback: bool = False,
) -> Path:
    """Resolve a path reference relative to base_path when provided."""
    path = Path(path_ref).expanduser()
    if not path.is_absolute():
        if base_path is None:
            if allow_cwd_fallback:
                return path.resolve()
            if error_message is None:
                raise ValueError("path ref uses a relative path but no base path was provided")
            raise ValueError(error_message)
        return (base_path / path).resolve()
    return path.resolve()
