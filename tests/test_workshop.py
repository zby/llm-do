"""Tests for workshop detection and configuration (worker-function architecture)."""

import pytest
from pathlib import Path

from llm_do.workshop import (
    InvalidWorkshopError,
    WorkshopContext,
    detect_invocation_mode,
    load_workshop_config,
    resolve_workshop,
)
from llm_do.types import InvocationMode, WorkshopConfig
from llm_do.registry import WorkerRegistry


class TestDetectInvocationMode:
    """Tests for detect_invocation_mode function."""

    def test_single_worker_file(self, tmp_path):
        """Test detection of single .worker file."""
        worker_file = tmp_path / "task.worker"
        worker_file.write_text("---\nname: task\n---\nInstructions here")

        mode = detect_invocation_mode(str(worker_file))
        assert mode == InvocationMode.SINGLE_FILE

    def test_workshop_with_main_worker(self, tmp_path):
        """Test detection of workshop directory with main.worker."""
        workshop_dir = tmp_path / "my-workshop"
        workshop_dir.mkdir()
        (workshop_dir / "main.worker").write_text("---\nname: main\n---\nMain worker")

        mode = detect_invocation_mode(str(workshop_dir))
        assert mode == InvocationMode.WORKSHOP

    def test_workshop_with_workshop_yaml(self, tmp_path):
        """Test detection of workshop directory with workshop.yaml only."""
        workshop_dir = tmp_path / "my-workshop"
        workshop_dir.mkdir()
        (workshop_dir / "workshop.yaml").write_text("name: my-workshop")
        # Note: This is technically invalid (no main.worker), but detection should work

        mode = detect_invocation_mode(str(workshop_dir))
        assert mode == InvocationMode.WORKSHOP

    def test_directory_without_markers_raises(self, tmp_path):
        """Test that directory without workshop markers raises error."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(InvalidWorkshopError) as exc_info:
            detect_invocation_mode(str(empty_dir))

        assert "not a valid workshop" in str(exc_info.value)
        assert "missing main.worker" in str(exc_info.value)

    def test_worker_name_returns_search_path(self):
        """Test that non-path argument returns SEARCH_PATH mode."""
        mode = detect_invocation_mode("my-worker")
        assert mode == InvocationMode.SEARCH_PATH

    def test_nonexistent_path_returns_search_path(self):
        """Test that nonexistent path is treated as worker name."""
        mode = detect_invocation_mode("nonexistent/path")
        assert mode == InvocationMode.SEARCH_PATH


class TestLoadWorkshopConfig:
    """Tests for load_workshop_config function."""

    def test_empty_workshop_no_yaml(self, tmp_path):
        """Test that missing workshop.yaml returns empty config."""
        config = load_workshop_config(tmp_path)
        assert config == WorkshopConfig()

    def test_minimal_workshop_yaml(self, tmp_path):
        """Test loading minimal workshop.yaml."""
        (tmp_path / "workshop.yaml").write_text("name: my-workshop")

        config = load_workshop_config(tmp_path)
        assert config.name == "my-workshop"
        assert config.model is None

    def test_full_workshop_yaml(self, tmp_path):
        """Test loading workshop.yaml with all fields."""
        yaml_content = """
name: my-workshop
version: 1.0.0
description: A test workshop
model: anthropic:claude-haiku-4-5
toolsets:
  filesystem: {}
  shell:
    rules: []
"""
        (tmp_path / "workshop.yaml").write_text(yaml_content)

        config = load_workshop_config(tmp_path)
        assert config.name == "my-workshop"
        assert config.version == "1.0.0"
        assert config.description == "A test workshop"
        assert config.model == "anthropic:claude-haiku-4-5"
        assert config.toolsets == {"filesystem": {}, "shell": {"rules": []}}


    def test_invalid_yaml_raises(self, tmp_path):
        """Test that invalid YAML raises ValueError."""
        (tmp_path / "workshop.yaml").write_text("invalid: yaml: syntax:")

        with pytest.raises(ValueError) as exc_info:
            load_workshop_config(tmp_path)

        assert "Invalid YAML" in str(exc_info.value)

    def test_invalid_schema_raises(self, tmp_path):
        """Test that schema violations raise ValueError."""
        # toolsets should be a dict, not a string
        (tmp_path / "workshop.yaml").write_text("toolsets: not-a-dict")

        with pytest.raises(ValueError) as exc_info:
            load_workshop_config(tmp_path)

        assert "Invalid workshop configuration" in str(exc_info.value)


class TestResolveWorkshop:
    """Tests for resolve_workshop function."""

    def test_resolve_workshop_directory(self, tmp_path):
        """Test resolving a workshop directory."""
        workshop_dir = tmp_path / "my-workshop"
        workshop_dir.mkdir()
        (workshop_dir / "main.worker").write_text("---\nname: main\n---\nMain")

        mode, context, worker_name = resolve_workshop(str(workshop_dir))

        assert mode == InvocationMode.WORKSHOP
        assert context is not None
        assert context.workshop_root == workshop_dir.resolve()
        assert worker_name == "main"

    def test_resolve_workshop_with_entry_override(self, tmp_path):
        """Test resolving workshop with --entry override."""
        workshop_dir = tmp_path / "my-workshop"
        workshop_dir.mkdir()
        (workshop_dir / "main.worker").write_text("---\nname: main\n---\nMain")

        mode, context, worker_name = resolve_workshop(
            str(workshop_dir),
            entry_override="custom_entry"
        )

        assert mode == InvocationMode.WORKSHOP
        assert worker_name == "custom_entry"
        assert context.entry_worker == "custom_entry"

    def test_resolve_single_file(self, tmp_path):
        """Test resolving a single worker file."""
        worker_file = tmp_path / "task.worker"
        worker_file.write_text("---\nname: task\n---\nTask worker")

        mode, context, worker_name = resolve_workshop(str(worker_file))

        assert mode == InvocationMode.SINGLE_FILE
        assert context is None
        assert worker_name == str(worker_file.resolve())

    def test_resolve_worker_name(self):
        """Test resolving a worker name (search path mode)."""
        mode, context, worker_name = resolve_workshop("my-worker")

        assert mode == InvocationMode.SEARCH_PATH
        assert context is None
        assert worker_name == "my-worker"


class TestRegistryWorkshopConfigInheritance:
    """Tests for workshop config inheritance in WorkerRegistry."""

    def test_registry_without_workshop_config(self, tmp_path):
        """Test that registry works without workshop config."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\nmodel: openai:gpt-4o\n---\nTest worker"
        )

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("test")

        assert definition.name == "test"
        assert definition.model == "openai:gpt-4o"

    def test_registry_inherits_workshop_model(self, tmp_path):
        """Test that worker inherits model from workshop config."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\n---\nTest worker"
        )

        workshop_config = WorkshopConfig(model="anthropic:claude-haiku-4-5")
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        definition = registry.load_definition("test")

        assert definition.model == "anthropic:claude-haiku-4-5"

    def test_worker_model_overrides_workshop(self, tmp_path):
        """Test that worker's own model overrides workshop config."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\nmodel: openai:gpt-4o\n---\nTest worker"
        )

        workshop_config = WorkshopConfig(model="anthropic:claude-haiku-4-5")
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        definition = registry.load_definition("test")

        assert definition.model == "openai:gpt-4o"

    def test_registry_merges_toolsets(self, tmp_path):
        """Test that toolsets are deep merged (workshop + worker)."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\ntoolsets:\n  custom:\n    tools:\n      my_tool: {}\n---\n"
        )

        workshop_config = WorkshopConfig(
            toolsets={"filesystem": {}, "shell": {"rules": []}}
        )
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        definition = registry.load_definition("test")

        # Should have all three toolsets
        assert "filesystem" in definition.toolsets
        assert "shell" in definition.toolsets
        assert "custom" in definition.toolsets

    def test_worker_toolsets_override_workshop(self, tmp_path):
        """Test that worker's toolset config overrides workshop's same-named toolset."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\ntoolsets:\n  shell:\n    rules:\n      - pattern: echo\n---\n"
        )

        workshop_config = WorkshopConfig(
            toolsets={"shell": {"rules": []}}
        )
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        definition = registry.load_definition("test")

        # Worker's shell config should override
        assert definition.toolsets["shell"]["rules"] == [{"pattern": "echo"}]


    def test_main_worker_at_workshop_root(self, tmp_path):
        """Test that main.worker at workshop root is found."""
        (tmp_path / "main.worker").write_text(
            "---\nname: main\n---\nMain entry point"
        )

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("main")

        assert definition.name == "main"
        assert definition.instructions == "Main entry point"


class TestPhase2TemplateSearchPaths:
    """Tests for Phase 2: Template search paths."""

    def test_worker_local_templates(self, tmp_path):
        """Test that worker-local templates are found."""
        # Create workshop structure
        workers_dir = tmp_path / "workers" / "templated"
        workers_dir.mkdir(parents=True)

        # Create worker with template include
        (workers_dir / "worker.worker").write_text(
            "---\nname: templated\n---\n{% include 'header.jinja' %}\nMain content"
        )

        # Create worker-local template
        (workers_dir / "header.jinja").write_text("# Worker Header\n")

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("templated")

        assert "# Worker Header" in definition.instructions
        assert "Main content" in definition.instructions

    def test_workshop_templates_directory(self, tmp_path):
        """Test that workshop templates/ directory is searched."""
        # Create workshop structure
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create worker with template include
        (workers_dir / "test.worker").write_text(
            "---\nname: test\n---\n{% include 'shared.jinja' %}"
        )

        # Create workshop-level template
        (templates_dir / "shared.jinja").write_text("Shared workshop content")

        # Need workshop config to enable workshop templates
        workshop_config = WorkshopConfig()
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        definition = registry.load_definition("test")

        assert "Shared workshop content" in definition.instructions

    def test_worker_templates_override_workshop(self, tmp_path):
        """Test that worker-local templates take precedence over workshop templates."""
        # Create structure
        workers_dir = tmp_path / "workers" / "override"
        workers_dir.mkdir(parents=True)
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create worker
        (workers_dir / "worker.worker").write_text(
            "---\nname: override\n---\n{% include 'common.jinja' %}"
        )

        # Create worker-local template (should win)
        (workers_dir / "common.jinja").write_text("Worker version")

        # Create workshop template
        (templates_dir / "common.jinja").write_text("Workshop version")

        workshop_config = WorkshopConfig()
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        definition = registry.load_definition("override")

        assert "Worker version" in definition.instructions


class TestWorkshopLevelTools:
    """Tests for workshop-level tools.py discovery."""

    def test_find_custom_tools_at_workshop_root(self, tmp_path):
        """Test that tools.py at workshop root is found in workshop mode."""
        # Create main.worker at root
        (tmp_path / "main.worker").write_text("---\nname: main\n---\nMain worker")

        # Create tools.py at workshop root
        (tmp_path / "tools.py").write_text("def my_tool(): pass")

        # Without workshop_config, tools should NOT be found
        registry = WorkerRegistry(tmp_path)
        assert registry.find_custom_tools("main") is None

        # With workshop_config, tools SHOULD be found
        workshop_config = WorkshopConfig()
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        tools_path = registry.find_custom_tools("main")

        assert tools_path is not None
        assert tools_path == tmp_path / "tools.py"

    def test_worker_tools_take_precedence_over_workshop(self, tmp_path):
        """Test that worker-level tools.py takes precedence over workshop-level."""
        # Create directory-form worker with its own tools
        worker_dir = tmp_path / "workers" / "myworker"
        worker_dir.mkdir(parents=True)
        (worker_dir / "worker.worker").write_text("---\nname: myworker\n---\n")
        (worker_dir / "tools.py").write_text("def worker_tool(): pass")

        # Create workshop-level tools
        (tmp_path / "tools.py").write_text("def workshop_tool(): pass")

        workshop_config = WorkshopConfig()
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        tools_path = registry.find_custom_tools("myworker")

        # Worker-level tools should win
        assert tools_path == worker_dir / "tools.py"

    def test_simple_worker_uses_workshop_tools(self, tmp_path):
        """Test that simple-form workers can use workshop-level tools."""
        # Create simple-form worker (not directory-based)
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "simple.worker").write_text("---\nname: simple\n---\n")

        # Create workshop-level tools
        (tmp_path / "tools.py").write_text("def shared_tool(): pass")

        workshop_config = WorkshopConfig()
        registry = WorkerRegistry(tmp_path, workshop_config=workshop_config)
        tools_path = registry.find_custom_tools("simple")

        # Workshop-level tools should be found
        assert tools_path == tmp_path / "tools.py"


class TestPhase2ExplicitPathSyntax:
    """Tests for Phase 2: Explicit path syntax (./workers/helper)."""

    def test_explicit_path_simple_form(self, tmp_path):
        """Test ./path/to/worker resolves to simple form."""
        workers_dir = tmp_path / "workers" / "nested"
        workers_dir.mkdir(parents=True)
        (workers_dir / "helper.worker").write_text("---\nname: helper\n---\nHelper worker")

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("./workers/nested/helper")

        assert definition.name == "helper"
        assert definition.instructions == "Helper worker"

    def test_explicit_path_directory_form(self, tmp_path):
        """Test ./path/to/worker resolves to directory form."""
        worker_dir = tmp_path / "workers" / "complex_helper"
        worker_dir.mkdir(parents=True)
        (worker_dir / "worker.worker").write_text("---\nname: complex_helper\n---\nComplex")

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("./workers/complex_helper")

        assert definition.name == "complex_helper"

    def test_parent_directory_rejected(self, tmp_path):
        """Test that ../ paths are rejected."""
        (tmp_path / "main.worker").write_text("---\nname: main\n---\n")

        registry = WorkerRegistry(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            registry.load_definition("../other/worker")

        assert "Parent directory references" in str(exc_info.value)

    def test_library_reference_not_yet_supported(self, tmp_path):
        """Test that lib:worker syntax raises informative error."""
        (tmp_path / "main.worker").write_text("---\nname: main\n---\n")

        registry = WorkerRegistry(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            registry.load_definition("utils:summarizer")

        assert "not yet supported" in str(exc_info.value)
