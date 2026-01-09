"""Worker file parsing (.worker format).

Worker files use YAML frontmatter followed by markdown instructions:

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  shell_readonly: {}
  calc_tools: {}
---
Instructions for the worker...
```

The `toolsets` section maps toolset names to empty config dicts.
Toolset names can reference:
- Built-in toolsets (e.g., "shell_readonly", "filesystem_rw")
- Toolsets discovered from Python files passed to CLI
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter


@dataclass
class WorkerDefinition:
    """Parsed worker definition from a .worker file.

    This is the declarative specification extracted from a .worker file,
    containing unresolved toolset references (as strings) that will be
    resolved to actual AbstractToolset instances when building a Worker.
    """
    name: str
    description: str | None
    instructions: str
    model: str | None = None
    compatible_models: list[str] | None = None
    schema_in_ref: str | None = None
    toolsets: dict[str, dict[str, Any]] = field(default_factory=dict)
    server_side_tools: list[dict[str, Any]] = field(default_factory=list)  # Raw config passed to PydanticAI


def _extract_frontmatter_and_instructions(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and instructions from worker file content.

    Returns:
        Tuple of (frontmatter dict, instructions string)

    Raises:
        ValueError: If file format is invalid
    """
    post = frontmatter.loads(content)

    # python-frontmatter returns empty dict for missing/invalid frontmatter
    if not post.metadata:
        raise ValueError("Invalid worker file format: missing frontmatter")

    return dict(post.metadata), post.content.strip()


def _parse_toolsets(toolsets_raw: Any) -> dict[str, dict[str, Any]]:
    """Parse and validate the toolsets section.

    Args:
        toolsets_raw: Raw toolsets value from frontmatter

    Returns:
        Normalized toolsets dict mapping names to empty config dicts

    Raises:
        ValueError: If toolsets format is invalid
    """
    if not toolsets_raw:
        return {}

    if not isinstance(toolsets_raw, dict):
        raise ValueError("Invalid toolsets: expected YAML mapping")

    toolsets: dict[str, dict[str, Any]] = {}
    for toolset_name, toolset_config in toolsets_raw.items():
        if toolset_config is None:
            toolset_config = {}
        if not isinstance(toolset_config, dict):
            raise ValueError(f"Invalid config for toolset '{toolset_name}': expected YAML mapping")
        if toolset_config:
            raise ValueError(
                f"Toolset '{toolset_name}' cannot be configured in worker YAML; "
                "define a Python toolset instance instead"
            )
        toolsets[toolset_name] = toolset_config

    return toolsets


def _parse_server_side_tools(raw: Any) -> list[dict[str, Any]]:
    """Parse and validate the server_side_tools section.

    Args:
        raw: Raw server_side_tools value from frontmatter

    Returns:
        List of server-side tool configurations

    Raises:
        ValueError: If format is invalid
    """
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError("Invalid server_side_tools: expected YAML list")
    return raw


def _parse_compatible_models(raw: Any) -> list[str] | None:
    """Parse and validate the compatible_models section.

    Args:
        raw: Raw compatible_models value from frontmatter

    Returns:
        List of compatible model patterns, or None if not specified

    Raises:
        ValueError: If format is invalid
    """
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("Invalid compatible_models: expected YAML list")
    return raw


def _parse_schema_ref(raw: Any) -> str | None:
    """Parse and validate a schema reference."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("Invalid schema_in_ref: expected string")
    if not raw.strip():
        raise ValueError("Invalid schema_in_ref: must not be empty")
    return raw


class WorkerFileParser:
    """Parser for .worker files.

    Parses YAML frontmatter + Markdown instructions format into WorkerDefinition.
    """

    def parse(
        self,
        content: str,
        overrides: list[str] | None = None,
    ) -> WorkerDefinition:
        """Parse worker file content.

        Args:
            content: Raw file content
            overrides: Optional list of --set KEY=VALUE overrides to apply

        Returns:
            Parsed WorkerDefinition

        Raises:
            ValueError: If file format is invalid
        """
        from ..config import apply_overrides

        fm, instructions = _extract_frontmatter_and_instructions(content)

        # Apply CLI overrides to frontmatter
        if overrides:
            fm = apply_overrides(fm, overrides)

        name = fm.get("name")
        if not name:
            raise ValueError("Worker file must have a 'name' field")

        return WorkerDefinition(
            name=name,
            description=fm.get("description"),
            instructions=instructions,
            model=fm.get("model"),
            compatible_models=_parse_compatible_models(fm.get("compatible_models")),
            schema_in_ref=_parse_schema_ref(fm.get("schema_in_ref")),
            toolsets=_parse_toolsets(fm.get("toolsets")),
            server_side_tools=_parse_server_side_tools(fm.get("server_side_tools")),
        )

    def load(
        self,
        path: str | Path,
        overrides: list[str] | None = None,
    ) -> WorkerDefinition:
        """Load and parse a worker file from disk.

        Args:
            path: Path to worker file
            overrides: Optional list of --set KEY=VALUE overrides to apply

        Returns:
            Parsed WorkerDefinition
        """
        content = Path(path).read_text(encoding="utf-8")
        return self.parse(content, overrides=overrides)


# Default parser instance
_default_parser = WorkerFileParser()


def parse_worker_file(
    content: str,
    overrides: list[str] | None = None,
) -> WorkerDefinition:
    """Parse a worker file with YAML frontmatter and markdown instructions.

    This is a convenience function that uses the default WorkerFileParser.

    Args:
        content: Raw file content
        overrides: Optional list of --set KEY=VALUE overrides to apply

    Returns:
        Parsed WorkerDefinition

    Raises:
        ValueError: If file format is invalid
    """
    return _default_parser.parse(content, overrides=overrides)


def load_worker_file(
    path: str | Path,
    overrides: list[str] | None = None,
) -> WorkerDefinition:
    """Load and parse a worker file from disk.

    This is a convenience function that uses the default WorkerFileParser.

    Args:
        path: Path to worker file
        overrides: Optional list of --set KEY=VALUE overrides to apply

    Returns:
        Parsed WorkerDefinition
    """
    return _default_parser.load(path, overrides=overrides)
