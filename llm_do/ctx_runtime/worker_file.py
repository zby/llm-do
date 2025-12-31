"""Worker file parsing (.worker format).

Worker files use YAML frontmatter followed by markdown instructions:

```yaml
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  shell: {}
  calc_tools: {}
---
Instructions for the worker...
```

The `toolsets` section maps toolset class paths (or aliases) to their configuration.
Toolset entries can reference:
- Built-in aliases (e.g., "shell", "filesystem")
- Fully-qualified class paths (e.g., ``llm_do.toolsets.shell.ShellToolset``)
- Toolsets discovered from Python files passed to CLI
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class WorkerFile:
    """Parsed worker file."""
    name: str
    description: str | None
    instructions: str
    model: str | None = None
    toolsets: dict[str, dict[str, Any]] = field(default_factory=dict)
    server_side_tools: list[dict[str, Any]] = field(default_factory=list)  # Raw config passed to PydanticAI


def parse_worker_file(
    content: str,
    overrides: list[str] | None = None,
) -> WorkerFile:
    """Parse a worker file with YAML frontmatter and markdown instructions.

    Args:
        content: Raw file content
        overrides: Optional list of --set KEY=VALUE overrides to apply

    Returns:
        Parsed WorkerFile

    Raises:
        ValueError: If file format is invalid
    """
    from ..config_overrides import apply_overrides

    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        raise ValueError("Invalid worker file format: missing frontmatter")

    frontmatter_str, instructions = match.groups()
    frontmatter = yaml.safe_load(frontmatter_str)

    if not isinstance(frontmatter, dict):
        raise ValueError("Invalid frontmatter: expected YAML mapping")

    # Apply CLI overrides to frontmatter
    if overrides:
        frontmatter = apply_overrides(frontmatter, overrides)

    name = frontmatter.get("name")
    if not name:
        raise ValueError("Worker file must have a 'name' field")

    # Parse toolsets section
    toolsets_raw = frontmatter.get("toolsets", {})
    toolsets: dict[str, dict[str, Any]] = {}

    if toolsets_raw:
        if not isinstance(toolsets_raw, dict):
            raise ValueError("Invalid toolsets: expected YAML mapping")

        for toolset_name, toolset_config in toolsets_raw.items():
            if toolset_config is None:
                toolset_config = {}
            if not isinstance(toolset_config, dict):
                raise ValueError(f"Invalid config for toolset '{toolset_name}': expected YAML mapping")
            toolsets[toolset_name] = toolset_config

    # Parse server_side_tools section (pass through to PydanticAI)
    server_side_tools = frontmatter.get("server_side_tools", [])
    if server_side_tools and not isinstance(server_side_tools, list):
        raise ValueError("Invalid server_side_tools: expected YAML list")

    return WorkerFile(
        name=name,
        description=frontmatter.get("description"),
        instructions=instructions.strip(),
        model=frontmatter.get("model"),
        toolsets=toolsets,
        server_side_tools=server_side_tools,
    )


def load_worker_file(
    path: str | Path,
    overrides: list[str] | None = None,
) -> WorkerFile:
    """Load and parse a worker file from disk.

    Args:
        path: Path to worker file
        overrides: Optional list of --set KEY=VALUE overrides to apply

    Returns:
        Parsed WorkerFile
    """
    content = Path(path).read_text(encoding="utf-8")
    return parse_worker_file(content, overrides=overrides)
