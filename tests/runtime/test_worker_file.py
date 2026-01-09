"""Tests for worker file parsing."""
import pytest

from llm_do.runtime import WorkerDefinition, WorkerFileParser, parse_worker_file


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
schema_in_ref: schemas.py:TopicInput
toolsets:
  shell_readonly: {}
  calc_tools: {}
---
You are a helpful assistant.
"""
        result = parse_worker_file(content)

        assert result.name == "main"
        assert result.schema_in_ref == "schemas.py:TopicInput"
        assert "shell_readonly" in result.toolsets
        assert "calc_tools" in result.toolsets
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
        """Test that invalid frontmatter (list instead of mapping) raises ValueError."""
        content = """\
---
- this
- is
- a list
---
Instructions.
"""
        # python-frontmatter treats non-dict frontmatter as missing
        with pytest.raises(ValueError, match="missing frontmatter"):
            parse_worker_file(content)

    def test_invalid_toolsets_raises(self):
        """Test that invalid toolsets section raises ValueError."""
        content = """\
---
name: main
toolsets:
  - shell_readonly
  - filesystem_rw
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
  shell_readonly: not_a_dict
---
Instructions.
"""
        with pytest.raises(ValueError, match="expected YAML mapping"):
            parse_worker_file(content)

    def test_toolset_config_not_allowed(self):
        """Test that non-empty toolset config raises ValueError."""
        content = """\
---
name: main
toolsets:
  shell_readonly:
    rules:
      - pattern: ls
        approval_required: false
---
Instructions.
"""
        with pytest.raises(ValueError, match="cannot be configured"):
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

    def test_server_side_tools_web_search(self):
        """Test parsing server_side_tools with web_search."""
        content = """\
---
name: searcher
model: anthropic:claude-haiku-4-5
server_side_tools:
  - tool_type: web_search
    max_uses: 3
---
Use web search to find information.
"""
        result = parse_worker_file(content)

        assert result.name == "searcher"
        assert len(result.server_side_tools) == 1
        assert result.server_side_tools[0]["tool_type"] == "web_search"
        assert result.server_side_tools[0]["max_uses"] == 3

    def test_server_side_tools_with_domains(self):
        """Test parsing server_side_tools with domain filtering."""
        content = """\
---
name: searcher
server_side_tools:
  - tool_type: web_search
    allowed_domains:
      - wikipedia.org
      - docs.python.org
---
Instructions.
"""
        result = parse_worker_file(content)

        assert len(result.server_side_tools) == 1
        tool = result.server_side_tools[0]
        assert tool["tool_type"] == "web_search"
        assert tool["allowed_domains"] == ["wikipedia.org", "docs.python.org"]

    def test_server_side_tools_multiple(self):
        """Test parsing multiple server_side_tools."""
        content = """\
---
name: enhanced
server_side_tools:
  - tool_type: web_search
  - tool_type: code_execution
  - tool_type: image_generation
---
Instructions.
"""
        result = parse_worker_file(content)

        assert len(result.server_side_tools) == 3
        types = [t["tool_type"] for t in result.server_side_tools]
        assert "web_search" in types
        assert "code_execution" in types
        assert "image_generation" in types

    def test_server_side_tools_invalid_format_raises(self):
        """Test that invalid server_side_tools format raises ValueError."""
        content = """\
---
name: main
server_side_tools:
  web_search: {}
---
Instructions.
"""
        with pytest.raises(ValueError, match="expected YAML list"):
            parse_worker_file(content)

    def test_server_side_tools_defaults_to_empty_list(self):
        """Test that server_side_tools defaults to empty list."""
        content = """\
---
name: basic
---
Instructions.
"""
        result = parse_worker_file(content)

        assert result.server_side_tools == []

    def test_compatible_models(self):
        """Test parsing compatible_models from worker file."""
        content = """\
---
name: strict_worker
model: anthropic:claude-sonnet-4-20250514
compatible_models:
  - anthropic:claude-sonnet-4-20250514
  - anthropic:claude-opus-4-20250514
  - openai:gpt-4o
---
Instructions.
"""
        result = parse_worker_file(content)

        assert result.compatible_models == [
            "anthropic:claude-sonnet-4-20250514",
            "anthropic:claude-opus-4-20250514",
            "openai:gpt-4o",
        ]

    def test_compatible_models_invalid_format_raises(self):
        """Test that invalid compatible_models format raises ValueError."""
        content = """\
---
name: main
compatible_models: not-a-list
---
Instructions.
"""
        with pytest.raises(ValueError, match="expected YAML list"):
            parse_worker_file(content)

    def test_schema_in_ref_invalid_format_raises(self):
        """Test that invalid schema_in_ref format raises ValueError."""
        content = """\
---
name: main
schema_in_ref:
  - not-a-string
---
Instructions.
"""
        with pytest.raises(ValueError, match="schema_in_ref"):
            parse_worker_file(content)

    def test_compatible_models_defaults_to_none(self):
        """Test that compatible_models defaults to None."""
        content = """\
---
name: basic
---
Instructions.
"""
        result = parse_worker_file(content)

        assert result.compatible_models is None


class TestWorkerFileParser:
    """Tests for WorkerFileParser class."""

    def test_parser_parse_returns_worker_definition(self):
        """Test that parser.parse() returns a WorkerDefinition."""
        parser = WorkerFileParser()
        content = """\
---
name: test_worker
model: anthropic:claude-haiku-4-5
---
Instructions here.
"""
        result = parser.parse(content)

        assert isinstance(result, WorkerDefinition)
        assert result.name == "test_worker"
        assert result.model == "anthropic:claude-haiku-4-5"

    def test_parser_instance_reusable(self):
        """Test that a parser instance can be reused for multiple files."""
        parser = WorkerFileParser()

        content1 = """\
---
name: worker1
---
First worker.
"""
        content2 = """\
---
name: worker2
---
Second worker.
"""
        result1 = parser.parse(content1)
        result2 = parser.parse(content2)

        assert result1.name == "worker1"
        assert result2.name == "worker2"
