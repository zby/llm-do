"""Worker file parsing (.worker format)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class WorkerFile:
    """Parsed worker file."""
    name: str
    description: str | None
    instructions: str
    model: str | None = None


def parse_worker_file(content: str) -> WorkerFile:
    """Parse a worker file with YAML frontmatter and markdown instructions."""
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        raise ValueError("Invalid worker file format: missing frontmatter")

    frontmatter_str, instructions = match.groups()
    frontmatter = yaml.safe_load(frontmatter_str)

    if not isinstance(frontmatter, dict):
        raise ValueError("Invalid frontmatter: expected YAML mapping")

    name = frontmatter.get("name")
    if not name:
        raise ValueError("Worker file must have a 'name' field")

    return WorkerFile(
        name=name,
        description=frontmatter.get("description"),
        instructions=instructions.strip(),
        model=frontmatter.get("model"),
    )


def load_worker_file(path: str | Path) -> WorkerFile:
    """Load and parse a worker file from disk."""
    content = Path(path).read_text(encoding="utf-8")
    return parse_worker_file(content)
