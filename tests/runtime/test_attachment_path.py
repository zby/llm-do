"""Unit tests for attachment path resolution."""
from pathlib import Path

import pytest

from llm_do.runtime.worker import _resolve_attachment_path


class TestResolveAttachmentPath:
    """Tests for _resolve_attachment_path helper."""

    def test_absolute_path_returned_as_is(self, tmp_path: Path) -> None:
        """Absolute paths should be returned unchanged (after normalization)."""
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        result = _resolve_attachment_path(str(test_file))
        assert result == test_file.resolve()

    def test_relative_path_with_base_path(self, tmp_path: Path) -> None:
        """Relative paths should be resolved against base_path."""
        subdir = tmp_path / "attachments"
        subdir.mkdir()
        test_file = subdir / "test.pdf"
        test_file.touch()

        result = _resolve_attachment_path("attachments/test.pdf", tmp_path)
        assert result == test_file.resolve()

    def test_relative_path_without_base_path(self) -> None:
        """Relative paths without base_path resolve from CWD."""
        result = _resolve_attachment_path("somefile.txt")
        expected = Path.cwd() / "somefile.txt"
        assert result == expected.resolve()

    def test_tilde_expansion(self, tmp_path: Path) -> None:
        """Home directory (~) should be expanded."""
        result = _resolve_attachment_path("~/test.pdf")
        assert "~" not in str(result)
        assert result.is_absolute()

    def test_base_path_tilde_expansion(self) -> None:
        """Base path with tilde should also be expanded."""
        result = _resolve_attachment_path("test.pdf", Path("~/mydir"))
        assert "~" not in str(result)
        assert result.is_absolute()


class TestRuntimeProjectRoot:
    """Tests for project_root in RuntimeConfig."""

    def test_runtime_config_project_root_default_none(self) -> None:
        """RuntimeConfig should have project_root=None by default."""
        from llm_do.runtime import Runtime

        runtime = Runtime()
        assert runtime.project_root is None

    def test_runtime_accepts_project_root(self, tmp_path: Path) -> None:
        """Runtime should accept and store project_root."""
        from llm_do.runtime import Runtime

        runtime = Runtime(project_root=tmp_path)
        assert runtime.project_root == tmp_path

    def test_runtime_config_stores_project_root(self, tmp_path: Path) -> None:
        """RuntimeConfig should store project_root."""
        from llm_do.runtime import Runtime

        runtime = Runtime(project_root=tmp_path)
        assert runtime.config.project_root == tmp_path
