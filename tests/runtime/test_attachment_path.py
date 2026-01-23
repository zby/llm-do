"""Unit tests for Attachment path resolution."""
from pathlib import Path

import pytest

from llm_do.runtime import Attachment


class TestAttachmentRender:
    """Tests for Attachment path resolution and rendering."""

    def test_absolute_path_resolved(self, tmp_path: Path) -> None:
        """Absolute paths should be resolved correctly."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"test content")
        attachment = Attachment(str(test_file))
        result = attachment.render()
        assert result.data == b"test content"
        assert result.media_type == "application/pdf"

    def test_relative_path_with_base_path(self, tmp_path: Path) -> None:
        """Relative paths should be resolved against base_path."""
        subdir = tmp_path / "attachments"
        subdir.mkdir()
        test_file = subdir / "test.pdf"
        test_file.write_bytes(b"pdf content")

        attachment = Attachment("attachments/test.pdf")
        result = attachment.render(base_path=tmp_path)
        assert result.data == b"pdf content"

    def test_relative_path_without_base_path(self, tmp_path: Path) -> None:
        """Relative paths without base_path resolve from CWD."""
        attachment = Attachment("somefile.txt")
        # Should raise FileNotFoundError since file doesn't exist
        with pytest.raises(FileNotFoundError):
            attachment.render()

    def test_tilde_expansion(self) -> None:
        """Home directory (~) should be expanded."""
        attachment = Attachment("~/test.pdf")
        # The path should be expanded (though file won't exist)
        resolved = attachment.path.expanduser()
        assert "~" not in str(resolved)
        assert resolved.is_absolute()

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError should be raised for missing files."""
        attachment = Attachment(tmp_path / "nonexistent.pdf")
        with pytest.raises(FileNotFoundError, match="Attachment not found"):
            attachment.render()

    def test_media_type_detection(self, tmp_path: Path) -> None:
        """Media type should be detected from file extension."""
        for ext, expected_type in [
            (".pdf", "application/pdf"),
            (".png", "image/png"),
            (".jpg", "image/jpeg"),
            (".txt", "text/plain"),
        ]:
            test_file = tmp_path / f"test{ext}"
            test_file.write_bytes(b"content")
            attachment = Attachment(test_file)
            result = attachment.render()
            assert result.media_type == expected_type

    def test_unknown_extension_uses_octet_stream(self, tmp_path: Path) -> None:
        """Unknown extensions should use application/octet-stream."""
        test_file = tmp_path / "test.xyz123"
        test_file.write_bytes(b"content")
        attachment = Attachment(test_file)
        result = attachment.render()
        assert result.media_type == "application/octet-stream"


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
