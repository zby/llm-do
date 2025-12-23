"""Tests for worker file parsing."""
import pytest

from llm_do.ctx_runtime import parse_worker_file, WorkerFile


class TestParseWorkerFile:
    """Tests for parse_worker_file function."""

    def test_basic_worker_file(self):
        """Test parsing a basic worker file."""
        content = """\
---
name: test_worker
model: anthropic:claude-haiku-4-5
---
These are the instructions.
"""
        result = parse_worker_file(content)

        assert result.name == "test_worker"
        assert result.model == "anthropic:claude-haiku-4-5"
        assert result.instructions == "These are the instructions."
        assert result.description is None
        assert result.toolsets == {}

    def test_worker_file_with_description(self):
        """Test parsing a worker file with description."""
        content = """\
---
name: my_worker
description: A helpful worker
model: openai:gpt-4o-mini
---
Instructions here.
"""
        result = parse_worker_file(content)

        assert result.name == "my_worker"
        assert result.description == "A helpful worker"
        assert result.model == "openai:gpt-4o-mini"

    def test_worker_file_with_toolsets(self):
        """Test parsing a worker file with toolsets section."""
        content = """\
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  shell:
    rules:
      - pattern: "^ls"
        allow: true
  calc_tools: {}
---
You are a helpful assistant.
"""
        result = parse_worker_file(content)

        assert result.name == "main"
        assert "shell" in result.toolsets
        assert "calc_tools" in result.toolsets
        assert result.toolsets["shell"]["rules"][0]["pattern"] == "^ls"
        assert result.toolsets["calc_tools"] == {}

    def test_worker_file_with_null_toolset_config(self):
        """Test parsing a worker file where toolset config is null/empty."""
        content = """\
---
name: main
model: anthropic:claude-haiku-4-5
toolsets:
  my_tools:
---
Instructions.
"""
        result = parse_worker_file(content)

        assert "my_tools" in result.toolsets
        assert result.toolsets["my_tools"] == {}

    def test_worker_file_multiline_instructions(self):
        """Test parsing a worker file with multiline instructions."""
        content = """\
---
name: main
model: test-model
---
Line 1.

Line 2.

Line 3.
"""
        result = parse_worker_file(content)

        assert "Line 1." in result.instructions
        assert "Line 2." in result.instructions
        assert "Line 3." in result.instructions

    def test_missing_frontmatter_raises(self):
        """Test that missing frontmatter raises ValueError."""
        content = "Just some text without frontmatter."

        with pytest.raises(ValueError, match="missing frontmatter"):
            parse_worker_file(content)

    def test_missing_name_raises(self):
        """Test that missing name field raises ValueError."""
        content = """\
---
model: test-model
---
Instructions.
"""
        with pytest.raises(ValueError, match="must have a 'name' field"):
            parse_worker_file(content)

    def test_invalid_frontmatter_raises(self):
        """Test that invalid frontmatter raises ValueError."""
        content = """\
---
- this
- is
- a list
---
Instructions.
"""
        with pytest.raises(ValueError, match="expected YAML mapping"):
            parse_worker_file(content)

    def test_invalid_toolsets_raises(self):
        """Test that invalid toolsets section raises ValueError."""
        content = """\
---
name: main
toolsets:
  - shell
  - filesystem
---
Instructions.
"""
        with pytest.raises(ValueError, match="expected YAML mapping"):
            parse_worker_file(content)

    def test_invalid_toolset_config_raises(self):
        """Test that invalid toolset config raises ValueError."""
        content = """\
---
name: main
toolsets:
  shell: not_a_dict
---
Instructions.
"""
        with pytest.raises(ValueError, match="expected YAML mapping"):
            parse_worker_file(content)

    def test_no_model(self):
        """Test parsing a worker file without a model."""
        content = """\
---
name: test_worker
---
Instructions.
"""
        result = parse_worker_file(content)

        assert result.name == "test_worker"
        assert result.model is None
