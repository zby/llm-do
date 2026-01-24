"""Worker file parsing (.worker format).

Worker files use YAML frontmatter followed by markdown instructions:

```yaml
---
name: main
entry: true
model: anthropic:claude-haiku-4-5
toolsets:
  - shell_readonly
  - calc_tools
---
Instructions for the worker...
```

The `toolsets` section is a list of toolset names.
Toolset names can reference:
- Built-in toolsets (e.g., "shell_readonly", "filesystem_project")
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
    resolved to ToolsetSpec factories when building an AgentSpec.
    """
    name: str
    description: str | None
    instructions: str
    model: str | None = None
    compatible_models: list[str] | None = None
    schema_in_ref: str | None = None
    entry: bool = False
    toolsets: list[str] = field(default_factory=list)
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


def build_worker_definition(
    frontmatter: dict[str, Any],
    instructions: str,
) -> "WorkerDefinition":
    """Build a WorkerDefinition from frontmatter and instructions."""
    fm = frontmatter

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
        entry=_parse_entry(fm.get("entry")),
        toolsets=_parse_toolsets(fm.get("toolsets")),
        server_side_tools=_parse_server_side_tools(fm.get("server_side_tools")),
    )


def load_worker_file_parts(path: str | Path) -> tuple[dict[str, Any], str]:
    """Load a worker file and return raw frontmatter and instructions."""
    content = Path(path).read_text(encoding="utf-8")
    return _extract_frontmatter_and_instructions(content)


def _parse_toolsets(toolsets_raw: Any) -> list[str]:
    """Parse and validate the toolsets section.

    Args:
        toolsets_raw: Raw toolsets value from frontmatter

    Returns:
        List of toolset names

    Raises:
        ValueError: If toolsets format is invalid
    """
    if toolsets_raw is None:
        return []

    if not isinstance(toolsets_raw, list):
        raise ValueError("Invalid toolsets: expected YAML list")

    toolsets: list[str] = []
    seen: set[str] = set()
    for item in toolsets_raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Invalid toolset entry: expected non-empty string")
        if item in seen:
            raise ValueError(f"Duplicate toolset entry: {item}")
        seen.add(item)
        toolsets.append(item)

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


def _parse_entry(raw: Any) -> bool:
    """Parse and validate the entry marker."""
    if raw is None:
        return False
    if not isinstance(raw, bool):
        raise ValueError("Invalid entry: expected boolean")
    return raw


class WorkerFileParser:
    """Parser for .worker files.

    Parses YAML frontmatter + Markdown instructions format into WorkerDefinition.
    """

    def parse(
        self,
        content: str,
    ) -> WorkerDefinition:
        """Parse worker file content.

        Args:
            content: Raw file content

        Returns:
            Parsed WorkerDefinition

        Raises:
            ValueError: If file format is invalid
        """
        fm, instructions = _extract_frontmatter_and_instructions(content)
        return build_worker_definition(fm, instructions)

    def load(
        self,
        path: str | Path,
    ) -> WorkerDefinition:
        """Load and parse a worker file from disk.

        Args:
            path: Path to worker file

        Returns:
            Parsed WorkerDefinition
        """
        content = Path(path).read_text(encoding="utf-8")
        return self.parse(content)


# Default parser instance
_default_parser = WorkerFileParser()


def parse_worker_file(
    content: str,
) -> WorkerDefinition:
    """Parse a worker file with YAML frontmatter and markdown instructions.

    This is a convenience function that uses the default WorkerFileParser.

    Args:
        content: Raw file content

    Returns:
        Parsed WorkerDefinition

    Raises:
        ValueError: If file format is invalid
    """
    return _default_parser.parse(content)


def load_worker_file(
    path: str | Path,
) -> WorkerDefinition:
    """Load and parse a worker file from disk.

    This is a convenience function that uses the default WorkerFileParser.

    Args:
        path: Path to worker file

    Returns:
        Parsed WorkerDefinition
    """
    return _default_parser.load(path)
