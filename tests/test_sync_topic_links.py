"""Tests for scripts/sync_topic_links.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the script importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from sync_topic_links import (
    build_topics_section,
    parse_areas,
    remove_topics_section,
    sync_note,
)


# --- parse_areas ---


class TestParseAreas:
    def test_inline_single(self):
        content = "---\nareas: [approvals-index]\n---\n\n# Title\n"
        assert parse_areas(content) == ["approvals-index"]

    def test_inline_multiple(self):
        content = "---\nareas: [approvals-index, pydanticai-upstream-index]\n---\n\n# Title\n"
        assert parse_areas(content) == ["approvals-index", "pydanticai-upstream-index"]

    def test_inline_empty_brackets(self):
        content = "---\nareas: []\n---\n\n# Title\n"
        assert parse_areas(content) == []

    def test_multiline_single(self):
        content = "---\nareas:\n  - index\n---\n\n# Title\n"
        assert parse_areas(content) == ["index"]

    def test_multiline_multiple(self):
        content = "---\nareas:\n  - index\n  - approvals-index\n---\n\n# Title\n"
        assert parse_areas(content) == ["index", "approvals-index"]

    def test_bare_areas_no_value(self):
        """areas: with nothing after it (empty, no brackets)."""
        content = "---\nareas:\n---\n\n# Title\n"
        assert parse_areas(content) == []

    def test_no_frontmatter(self):
        content = "# Title\n\nSome content.\n"
        assert parse_areas(content) == []

    def test_no_areas_field(self):
        content = "---\ndescription: A note\nstatus: current\n---\n\n# Title\n"
        assert parse_areas(content) == []

    def test_areas_with_extra_spaces(self):
        content = "---\nareas: [ approvals-index , index ]\n---\n\n# Title\n"
        assert parse_areas(content) == ["approvals-index", "index"]

    def test_areas_among_other_fields(self):
        content = (
            "---\n"
            "description: A test note\n"
            "type: insight\n"
            "areas: [approvals-index]\n"
            "status: current\n"
            "---\n"
            "\n# Title\n"
        )
        assert parse_areas(content) == ["approvals-index"]


# --- build_topics_section ---


class TestBuildTopicsSection:
    def test_single_area(self):
        result = build_topics_section(["approvals-index"])
        assert result == "Topics:\n- [approvals-index](./approvals-index.md)\n"

    def test_multiple_areas_sorted(self):
        result = build_topics_section(["pydanticai-upstream-index", "approvals-index"])
        assert result == (
            "Topics:\n"
            "- [approvals-index](./approvals-index.md)\n"
            "- [pydanticai-upstream-index](./pydanticai-upstream-index.md)\n"
        )

    def test_already_sorted(self):
        result = build_topics_section(["a-index", "b-index"])
        assert "- [a-index]" in result
        assert result.index("[a-index]") < result.index("[b-index]")


# --- remove_topics_section ---


class TestRemoveTopicsSection:
    def test_removes_topics_at_end(self):
        content = "Body text.\n\nTopics:\n- [index](./index.md)\n"
        result = remove_topics_section(content)
        # The regex removes \nTopics:..., leaving the preceding blank line
        assert result == "Body text.\n\n"
        assert "Topics:" not in result

    def test_removes_multi_item_topics(self):
        content = (
            "Body text.\n"
            "\n"
            "Topics:\n"
            "- [a](./a.md)\n"
            "- [b](./b.md)\n"
        )
        result = remove_topics_section(content)
        assert result == "Body text.\n\n"
        assert "Topics:" not in result

    def test_no_topics_unchanged(self):
        content = "Body text.\n\nRelevant Notes:\n- [a](./a.md)\n"
        result = remove_topics_section(content)
        assert result == content

    def test_preserves_relevant_notes_before_topics(self):
        content = (
            "---\n\n"
            "Relevant Notes:\n"
            "- [a](./a.md) — extends\n"
            "\n"
            "Topics:\n"
            "- [index](./index.md)\n"
        )
        result = remove_topics_section(content)
        assert "Relevant Notes:" in result
        assert "Topics:" not in result


# --- sync_note (integration) ---


class TestSyncNote:
    def _write_note(self, tmp_path: Path, name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    def test_adds_topics_to_note_with_areas_and_footer(self, tmp_path):
        content = (
            "---\n"
            "description: Test note\n"
            "areas: [approvals-index]\n"
            "---\n"
            "\n# Title\n"
            "\nBody.\n"
            "\n---\n"
            "\nRelevant Notes:\n"
            "- [a](./a.md) — extends\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        result = sync_note(p)

        assert result is not None
        assert "UPDATED" in result
        updated = p.read_text()
        assert "Topics:\n- [approvals-index](./approvals-index.md)\n" in updated
        assert "Relevant Notes:" in updated

    def test_adds_separator_when_missing(self, tmp_path):
        content = (
            "---\n"
            "areas: [index]\n"
            "---\n"
            "\n# Title\n"
            "\nBody content.\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        sync_note(p)

        updated = p.read_text()
        assert "\n---\n" in updated
        assert "Topics:\n- [index](./index.md)\n" in updated

    def test_replaces_wrong_topics(self, tmp_path):
        content = (
            "---\n"
            "areas: [approvals-index]\n"
            "---\n"
            "\n# Title\n"
            "\n---\n"
            "\nTopics:\n"
            "- [index](./index.md)\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        result = sync_note(p)

        assert result is not None
        updated = p.read_text()
        assert "[approvals-index](./approvals-index.md)" in updated
        assert "- [index](./index.md)" not in updated

    def test_removes_topics_when_no_areas(self, tmp_path):
        content = (
            "---\n"
            "description: Test\n"
            "---\n"
            "\n# Title\n"
            "\n---\n"
            "\nTopics:\n"
            "- [index](./index.md)\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        result = sync_note(p)

        assert result is not None
        assert "REMOVED" in result
        updated = p.read_text()
        assert "Topics:" not in updated

    def test_no_change_when_already_correct(self, tmp_path):
        content = (
            "---\n"
            "areas: [index]\n"
            "---\n"
            "\n# Title\n"
            "\n---\n"
            "\nTopics:\n"
            "- [index](./index.md)\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        result = sync_note(p)

        assert result is None

    def test_no_change_when_no_areas_no_topics(self, tmp_path):
        content = (
            "---\n"
            "description: Test\n"
            "---\n"
            "\n# Title\n"
            "\nBody.\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        result = sync_note(p)

        assert result is None

    def test_multiple_areas_sorted_in_output(self, tmp_path):
        content = (
            "---\n"
            "areas: [pydanticai-upstream-index, approvals-index]\n"
            "---\n"
            "\n# Title\n"
            "\n---\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        sync_note(p)

        updated = p.read_text()
        # Find positions in the Topics section only (not frontmatter)
        topics_start = updated.index("Topics:")
        topics_section = updated[topics_start:]
        a_pos = topics_section.index("approvals-index")
        p_pos = topics_section.index("pydanticai-upstream-index")
        assert a_pos < p_pos

    def test_dry_run_does_not_modify(self, tmp_path):
        content = (
            "---\n"
            "areas: [index]\n"
            "---\n"
            "\n# Title\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        result = sync_note(p, dry_run=True)

        assert result is not None
        assert "UPDATED" in result
        # File unchanged
        assert p.read_text() == content

    def test_multiline_areas_format(self, tmp_path):
        content = (
            "---\n"
            "areas:\n"
            "  - index\n"
            "  - approvals-index\n"
            "---\n"
            "\n# Title\n"
            "\n---\n"
        )
        p = self._write_note(tmp_path, "test.md", content)
        sync_note(p)

        updated = p.read_text()
        assert "[approvals-index](./approvals-index.md)" in updated
        assert "[index](./index.md)" in updated
