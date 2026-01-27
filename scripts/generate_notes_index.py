#!/usr/bin/env python3
"""Generate notes index from frontmatter.

Reads YAML frontmatter from markdown files and generates an index.
Frontmatter format:
---
description: One-line summary of the note
---
"""

import re
import sys
from pathlib import Path

import yaml


def parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content."""
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None


def get_title(content: str) -> str:
    """Extract first H1 heading from markdown."""
    # Skip frontmatter if present
    content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1) if match else "Untitled"


def generate_index(notes_dir: Path) -> str:
    """Generate markdown index from notes with frontmatter."""
    entries: list[tuple[str, str, str]] = []  # (path, title, desc)

    # Collect notes from main directory only
    for md_file in sorted(notes_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue

        content = md_file.read_text()
        frontmatter = parse_frontmatter(content)
        title = get_title(content)

        if frontmatter and "description" in frontmatter:
            desc = frontmatter["description"]
        else:
            desc = ""

        entries.append((md_file.name, title, desc))

    # Also check subdirectories (meta/, research/)
    subdirs = ["meta", "research"]
    subdir_entries: dict[str, list] = {d: [] for d in subdirs}

    for subdir in subdirs:
        subdir_path = notes_dir / subdir
        if not subdir_path.exists():
            continue
        for md_file in sorted(subdir_path.glob("*.md")):
            if md_file.name == "README.md":
                continue
            content = md_file.read_text()
            frontmatter = parse_frontmatter(content)
            title = get_title(content)

            if frontmatter and "description" in frontmatter:
                desc = frontmatter["description"]
            else:
                desc = ""

            subdir_entries[subdir].append((f"{subdir}/{md_file.name}", title, desc))

    # Generate markdown
    lines = ["## Index", ""]

    if entries:
        for path, title, desc in entries:
            suffix = f" — {desc}" if desc else ""
            lines.append(f"- [{title}]({path}){suffix}")
        lines.append("")

    for subdir in subdirs:
        if subdir_entries[subdir]:
            lines.append(f"### {subdir.title()}")
            lines.append("")
            for path, title, desc in subdir_entries[subdir]:
                suffix = f" — {desc}" if desc else ""
                lines.append(f"- [{title}]({path}){suffix}")
            lines.append("")

    return "\n".join(lines)


def main():
    notes_dir = Path(__file__).parent.parent / "docs" / "notes"
    if not notes_dir.exists():
        print(f"Notes directory not found: {notes_dir}", file=sys.stderr)
        sys.exit(1)

    index = generate_index(notes_dir)
    print(index)


if __name__ == "__main__":
    main()
