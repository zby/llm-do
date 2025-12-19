"""Tests for worker registry functionality."""

import pytest
from pathlib import Path

from llm_do.registry import WorkerRegistry


class TestRegistryWorkerSearch:
    """Tests for worker search in registry root."""

    def test_simple_form_at_root(self, tmp_path):
        """Test that workers at root are found (simple form)."""
        (tmp_path / "test.worker").write_text(
            "---\nname: test\nmodel: openai:gpt-4o\n---\nTest worker"
        )

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("test")

        assert definition.name == "test"
        assert definition.model == "openai:gpt-4o"

    def test_directory_form_at_root(self, tmp_path):
        """Test that directory-form workers at root are found."""
        worker_dir = tmp_path / "complex_worker"
        worker_dir.mkdir()
        (worker_dir / "worker.worker").write_text(
            "---\nname: complex_worker\n---\nComplex worker"
        )

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("complex_worker")

        assert definition.name == "complex_worker"

    def test_explicit_path_simple_form(self, tmp_path):
        """Test ./path/to/worker resolves to simple form."""
        workers_dir = tmp_path / "nested"
        workers_dir.mkdir(parents=True)
        (workers_dir / "helper.worker").write_text("---\nname: helper\n---\nHelper worker")

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("./nested/helper")

        assert definition.name == "helper"
        assert definition.instructions == "Helper worker"

    def test_explicit_path_directory_form(self, tmp_path):
        """Test ./path/to/worker resolves to directory form."""
        worker_dir = tmp_path / "nested" / "complex_helper"
        worker_dir.mkdir(parents=True)
        (worker_dir / "worker.worker").write_text("---\nname: complex_helper\n---\nComplex")

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("./nested/complex_helper")

        assert definition.name == "complex_helper"

    def test_parent_directory_rejected(self, tmp_path):
        """Test that ../ paths are rejected."""
        (tmp_path / "test.worker").write_text("---\nname: test\n---\n")

        registry = WorkerRegistry(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            registry.load_definition("../other/worker")

        assert "Parent directory references" in str(exc_info.value)

    def test_library_reference_not_yet_supported(self, tmp_path):
        """Test that lib:worker syntax raises informative error."""
        (tmp_path / "test.worker").write_text("---\nname: test\n---\n")

        registry = WorkerRegistry(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            registry.load_definition("utils:summarizer")

        assert "not yet supported" in str(exc_info.value)


class TestRegistryListWorkers:
    """Tests for listing workers in registry."""

    def test_list_workers_at_root(self, tmp_path):
        """Test that workers at root are listed."""
        (tmp_path / "worker_a.worker").write_text("---\nname: worker_a\n---\n")
        (tmp_path / "worker_b.worker").write_text("---\nname: worker_b\n---\n")

        registry = WorkerRegistry(tmp_path)
        workers = registry.list_workers()

        assert "worker_a" in workers
        assert "worker_b" in workers

    def test_list_workers_directory_form(self, tmp_path):
        """Test that directory-form workers at root are listed."""
        worker_dir = tmp_path / "dir_worker"
        worker_dir.mkdir()
        (worker_dir / "worker.worker").write_text("---\nname: dir_worker\n---\n")

        registry = WorkerRegistry(tmp_path)
        workers = registry.list_workers()

        assert "dir_worker" in workers


class TestRegistryCustomTools:
    """Tests for custom tools discovery at registry root."""

    def test_find_custom_tools_at_root(self, tmp_path):
        """Test that tools.py at registry root is found for simple workers."""
        (tmp_path / "simple.worker").write_text("---\nname: simple\n---\n")
        (tmp_path / "tools.py").write_text("def my_tool(): pass")

        registry = WorkerRegistry(tmp_path)
        tools_path = registry.find_custom_tools("simple")

        assert tools_path is not None
        assert tools_path == tmp_path / "tools.py"

    def test_worker_tools_take_precedence_over_root(self, tmp_path):
        """Test that worker-level tools.py takes precedence over root-level."""
        # Create directory-form worker with its own tools
        worker_dir = tmp_path / "myworker"
        worker_dir.mkdir()
        (worker_dir / "worker.worker").write_text("---\nname: myworker\n---\n")
        (worker_dir / "tools.py").write_text("def worker_tool(): pass")

        # Create root-level tools
        (tmp_path / "tools.py").write_text("def root_tool(): pass")

        registry = WorkerRegistry(tmp_path)
        tools_path = registry.find_custom_tools("myworker")

        # Worker-level tools should win
        assert tools_path == worker_dir / "tools.py"


class TestTemplateSearchPaths:
    """Tests for template search paths."""

    def test_worker_local_templates(self, tmp_path):
        """Test that worker-local templates are found."""
        # Create worker directory structure
        worker_dir = tmp_path / "templated"
        worker_dir.mkdir(parents=True)

        # Create worker with template include
        (worker_dir / "worker.worker").write_text(
            "---\nname: templated\n---\n{% include 'header.jinja' %}\nMain content"
        )

        # Create worker-local template
        (worker_dir / "header.jinja").write_text("# Worker Header\n")

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("templated")

        assert "# Worker Header" in definition.instructions
        assert "Main content" in definition.instructions
