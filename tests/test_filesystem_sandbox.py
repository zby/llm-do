"""Tests for filesystem sandbox functionality.

Tests the core sandbox file operations: reading, writing, suffix validation,
truncation, and offset handling. These tests focus on the Sandbox class
from worker_sandbox.py which wraps FileSandboxImpl from filesystem_sandbox.py.
"""
from __future__ import annotations

import pytest

from llm_do.worker_sandbox import Sandbox, SandboxConfig, SuffixNotAllowedError
from llm_do.filesystem_sandbox import PathConfig, ReadResult


class TestSandboxRead:
    """Tests for Sandbox.read() functionality."""

    def test_read_text_rejects_binary_suffix(self, tmp_path):
        """Sandbox should refuse to read files with disallowed suffixes."""
        sandbox_root = tmp_path / "input"
        sandbox_root.mkdir()
        binary_file = sandbox_root / "photo.png"
        binary_file.write_bytes(b"not actually an image")

        config = SandboxConfig(
            paths={
                "input": PathConfig(
                    root=str(sandbox_root),
                    mode="ro",
                    suffixes=[".txt"],
                )
            }
        )
        sandbox = Sandbox(config)

        with pytest.raises(SuffixNotAllowedError, match="suffix '.png' not allowed"):
            sandbox.read("input/photo.png")

    def test_read_returns_read_result(self, tmp_path):
        """Sandbox.read() returns ReadResult with content and metadata."""
        sandbox_root = tmp_path / "input"
        sandbox_root.mkdir()
        text_file = sandbox_root / "doc.txt"
        text_file.write_text("Hello, World!", encoding="utf-8")

        config = SandboxConfig(
            paths={
                "input": PathConfig(
                    root=str(sandbox_root),
                    mode="ro",
                )
            }
        )
        sandbox = Sandbox(config)

        result = sandbox.read("input/doc.txt")
        assert isinstance(result, ReadResult)
        assert result.content == "Hello, World!"
        assert result.truncated is False
        assert result.total_chars == 13
        assert result.offset == 0
        assert result.chars_read == 13

    def test_read_truncates_large_content(self, tmp_path):
        """Sandbox.read() truncates content when exceeding max_chars."""
        sandbox_root = tmp_path / "input"
        sandbox_root.mkdir()
        text_file = sandbox_root / "large.txt"
        content = "x" * 100
        text_file.write_text(content, encoding="utf-8")

        config = SandboxConfig(
            paths={
                "input": PathConfig(
                    root=str(sandbox_root),
                    mode="ro",
                )
            }
        )
        sandbox = Sandbox(config)

        result = sandbox.read("input/large.txt", max_chars=30)
        assert result.content == "x" * 30
        assert result.truncated is True
        assert result.total_chars == 100
        assert result.offset == 0
        assert result.chars_read == 30

    def test_read_with_offset(self, tmp_path):
        """Sandbox.read() respects offset parameter."""
        sandbox_root = tmp_path / "input"
        sandbox_root.mkdir()
        text_file = sandbox_root / "doc.txt"
        text_file.write_text("0123456789ABCDEF", encoding="utf-8")

        config = SandboxConfig(
            paths={
                "input": PathConfig(
                    root=str(sandbox_root),
                    mode="ro",
                )
            }
        )
        sandbox = Sandbox(config)

        result = sandbox.read("input/doc.txt", offset=10)
        assert result.content == "ABCDEF"
        assert result.truncated is False
        assert result.total_chars == 16
        assert result.offset == 10
        assert result.chars_read == 6

    def test_read_with_offset_and_max_chars(self, tmp_path):
        """Sandbox.read() respects both offset and max_chars."""
        sandbox_root = tmp_path / "input"
        sandbox_root.mkdir()
        text_file = sandbox_root / "doc.txt"
        text_file.write_text("0123456789ABCDEF", encoding="utf-8")

        config = SandboxConfig(
            paths={
                "input": PathConfig(
                    root=str(sandbox_root),
                    mode="ro",
                )
            }
        )
        sandbox = Sandbox(config)

        result = sandbox.read("input/doc.txt", max_chars=4, offset=10)
        assert result.content == "ABCD"
        assert result.truncated is True
        assert result.total_chars == 16
        assert result.offset == 10
        assert result.chars_read == 4
