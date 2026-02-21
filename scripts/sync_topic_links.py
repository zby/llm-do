#!/usr/bin/env python3
"""Sync Topics footer links from frontmatter areas: field.

Reads docs/notes/*.md, parses the areas: field from YAML frontmatter,
and generates/replaces the Topics: footer section with correct links.

This is a deterministic operation — areas: is the single source of truth.
"""

import re
import sys
from pathlib import Path

NOTES_DIR = Path(__file__).resolve().parent.parent / "docs" / "notes"


def parse_areas(content: str) -> list[str]:
    """Extract areas from YAML frontmatter.

    Handles:
      - areas: [val1, val2]
      - areas:
          - val1
          - val2
      - areas:          (empty — returns [])
    """
    # Match frontmatter block
    fm_match = re.match(r"^---\n(.*?\n)---\n", content, re.DOTALL)
    if not fm_match:
        return []
    frontmatter = fm_match.group(1)

    # Try inline format: areas: [val1, val2]
    inline = re.search(r"^areas:\s*\[([^\]]*)\]\s*$", frontmatter, re.MULTILINE)
    if inline:
        raw = inline.group(1).strip()
        if not raw:
            return []
        return [a.strip() for a in raw.split(",") if a.strip()]

    # Try multi-line format: areas:\n  - val1\n  - val2
    ml = re.search(r"^areas:\s*\n((?:\s+-\s+.*\n)*)", frontmatter, re.MULTILINE)
    if ml:
        items = re.findall(r"^\s+-\s+(.+)$", ml.group(1), re.MULTILINE)
        return [a.strip() for a in items if a.strip()]

    return []


def build_topics_section(areas: list[str]) -> str:
    """Build the Topics: footer section from a list of area names."""
    lines = ["Topics:"]
    for area in sorted(areas):
        lines.append(f"- [{area}](./{area}.md)")
    return "\n".join(lines) + "\n"


def remove_topics_section(content: str) -> str:
    """Remove existing Topics: section from content."""
    # Topics section: starts with "Topics:" line, followed by list items, until EOF or next section
    return re.sub(r"\nTopics:\n(?:- \[.*\]\(.*\)\n)*$", "\n", content)


def sync_note(filepath: Path, dry_run: bool = False) -> str | None:
    """Sync a single note's Topics section. Returns description of change, or None."""
    content = filepath.read_text()
    areas = parse_areas(content)

    # Remove existing Topics section (if any) to work with clean content
    cleaned = remove_topics_section(content)

    if not areas:
        if cleaned != content:
            # Had a Topics section that was removed
            # Also clean up trailing separator if it's now dangling
            cleaned = cleaned.rstrip("\n") + "\n"
            if not dry_run:
                filepath.write_text(cleaned)
            return f"  REMOVED Topics (no areas): {filepath.name}"
        return None

    # Build new Topics section
    topics = build_topics_section(areas)

    # Ensure content ends cleanly before appending
    cleaned = cleaned.rstrip("\n") + "\n"

    # Check if there's already a footer separator (--- at end area)
    # Look for --- followed by optional Relevant Notes section at end
    has_footer_sep = bool(re.search(r"\n---\n", cleaned))

    if not has_footer_sep:
        cleaned += "\n---\n"

    # Append Topics after a blank line
    cleaned += "\n" + topics

    if cleaned == content:
        return None

    if not dry_run:
        filepath.write_text(cleaned)
    return f"  UPDATED: {filepath.name} -> areas={areas}"


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("DRY RUN — no files will be modified\n")

    if not NOTES_DIR.is_dir():
        print(f"Error: {NOTES_DIR} not found", file=sys.stderr)
        sys.exit(1)

    # Check which index files exist
    all_areas = set()
    notes = sorted(NOTES_DIR.glob("*.md"))

    for note in notes:
        areas = parse_areas(note.read_text())
        all_areas.update(areas)

    print("Known areas referenced in frontmatter:")
    for area in sorted(all_areas):
        index_file = NOTES_DIR / f"{area}.md"
        status = "OK" if index_file.exists() else "WARNING: file not found!"
        print(f"  {area}.md — {status}")
    print()

    # Sync all notes
    changes = []
    for note in notes:
        result = sync_note(note, dry_run=dry_run)
        if result:
            changes.append(result)

    if changes:
        print(f"{'Would change' if dry_run else 'Changed'} {len(changes)} file(s):")
        for c in changes:
            print(c)
    else:
        print("All Topics sections are in sync.")


if __name__ == "__main__":
    main()
