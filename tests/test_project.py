"""Tests for project detection and configuration (Phase 1 of worker-function architecture)."""

import pytest
from pathlib import Path

from llm_do.project import (
    InvalidProjectError,
    ProjectContext,
    detect_invocation_mode,
    find_entry_worker_path,
    load_project_config,
    resolve_project,
)
from llm_do.types import InvocationMode, ProjectConfig
from llm_do.registry import WorkerRegistry
from llm_do.worker_sandbox import SandboxConfig, PathConfig


class TestDetectInvocationMode:
    """Tests for detect_invocation_mode function."""

    def test_single_worker_file(self, tmp_path):
        """Test detection of single .worker file."""
        worker_file = tmp_path / "task.worker"
        worker_file.write_text("---\nname: task\n---\nInstructions here")

        mode = detect_invocation_mode(str(worker_file))
        assert mode == InvocationMode.SINGLE_FILE

    def test_project_with_main_worker(self, tmp_path):
        """Test detection of project directory with main.worker."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / "main.worker").write_text("---\nname: main\n---\nMain worker")

        mode = detect_invocation_mode(str(project_dir))
        assert mode == InvocationMode.PROJECT

    def test_project_with_project_yaml(self, tmp_path):
        """Test detection of project directory with project.yaml only."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / "project.yaml").write_text("name: my-project")
        # Note: This is technically invalid (no main.worker), but detection should work

        mode = detect_invocation_mode(str(project_dir))
        assert mode == InvocationMode.PROJECT

    def test_directory_without_markers_raises(self, tmp_path):
        """Test that directory without project markers raises error."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(InvalidProjectError) as exc_info:
            detect_invocation_mode(str(empty_dir))

        assert "not a valid project" in str(exc_info.value)
        assert "missing main.worker" in str(exc_info.value)

    def test_worker_name_returns_search_path(self):
        """Test that non-path argument returns SEARCH_PATH mode."""
        mode = detect_invocation_mode("my-worker")
        assert mode == InvocationMode.SEARCH_PATH

    def test_nonexistent_path_returns_search_path(self):
        """Test that nonexistent path is treated as worker name."""
        mode = detect_invocation_mode("nonexistent/path")
        assert mode == InvocationMode.SEARCH_PATH


class TestLoadProjectConfig:
    """Tests for load_project_config function."""

    def test_empty_project_no_yaml(self, tmp_path):
        """Test that missing project.yaml returns empty config."""
        config = load_project_config(tmp_path)
        assert config == ProjectConfig()

    def test_minimal_project_yaml(self, tmp_path):
        """Test loading minimal project.yaml."""
        (tmp_path / "project.yaml").write_text("name: my-project")

        config = load_project_config(tmp_path)
        assert config.name == "my-project"
        assert config.model is None
        assert config.dependencies == []

    def test_full_project_yaml(self, tmp_path):
        """Test loading project.yaml with all fields."""
        yaml_content = """
name: my-project
version: 1.0.0
description: A test project
model: anthropic:claude-haiku-4-5
dependencies:
  - utils
  - legal@2.0
toolsets:
  filesystem: {}
  shell:
    rules: []
exports:
  - main
  - helper
"""
        (tmp_path / "project.yaml").write_text(yaml_content)

        config = load_project_config(tmp_path)
        assert config.name == "my-project"
        assert config.version == "1.0.0"
        assert config.description == "A test project"
        assert config.model == "anthropic:claude-haiku-4-5"
        assert config.dependencies == ["utils", "legal@2.0"]
        assert config.toolsets == {"filesystem": {}, "shell": {"rules": []}}
        assert config.exports == ["main", "helper"]

    def test_project_yaml_with_sandbox(self, tmp_path):
        """Test loading project.yaml with sandbox config."""
        yaml_content = """
name: sandboxed-project
sandbox:
  paths:
    input:
      root: ./input
      mode: ro
    output:
      root: ./output
      mode: rw
"""
        (tmp_path / "project.yaml").write_text(yaml_content)

        config = load_project_config(tmp_path)
        assert config.sandbox is not None
        assert "input" in config.sandbox.paths
        assert config.sandbox.paths["input"].mode == "ro"
        assert "output" in config.sandbox.paths
        assert config.sandbox.paths["output"].mode == "rw"

    def test_invalid_yaml_raises(self, tmp_path):
        """Test that invalid YAML raises ValueError."""
        (tmp_path / "project.yaml").write_text("invalid: yaml: syntax:")

        with pytest.raises(ValueError) as exc_info:
            load_project_config(tmp_path)

        assert "Invalid YAML" in str(exc_info.value)

    def test_invalid_schema_raises(self, tmp_path):
        """Test that schema violations raise ValueError."""
        (tmp_path / "project.yaml").write_text("model: 123")  # model should be string

        # Pydantic should coerce 123 to "123", but let's test with a more obvious violation
        (tmp_path / "project.yaml").write_text("sandbox:\n  paths: not-a-dict")

        with pytest.raises(ValueError) as exc_info:
            load_project_config(tmp_path)

        assert "Invalid project configuration" in str(exc_info.value)


class TestResolveProject:
    """Tests for resolve_project function."""

    def test_resolve_project_directory(self, tmp_path):
        """Test resolving a project directory."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / "main.worker").write_text("---\nname: main\n---\nMain")

        mode, context, worker_name = resolve_project(str(project_dir))

        assert mode == InvocationMode.PROJECT
        assert context is not None
        assert context.project_root == project_dir.resolve()
        assert worker_name == "main"

    def test_resolve_project_with_entry_override(self, tmp_path):
        """Test resolving project with --entry override."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / "main.worker").write_text("---\nname: main\n---\nMain")

        mode, context, worker_name = resolve_project(
            str(project_dir),
            entry_override="custom_entry"
        )

        assert mode == InvocationMode.PROJECT
        assert worker_name == "custom_entry"
        assert context.entry_worker == "custom_entry"

    def test_resolve_single_file(self, tmp_path):
        """Test resolving a single worker file."""
        worker_file = tmp_path / "task.worker"
        worker_file.write_text("---\nname: task\n---\nTask worker")

        mode, context, worker_name = resolve_project(str(worker_file))

        assert mode == InvocationMode.SINGLE_FILE
        assert context is None
        assert worker_name == str(worker_file.resolve())

    def test_resolve_worker_name(self):
        """Test resolving a worker name (search path mode)."""
        mode, context, worker_name = resolve_project("my-worker")

        assert mode == InvocationMode.SEARCH_PATH
        assert context is None
        assert worker_name == "my-worker"


class TestFindEntryWorkerPath:
    """Tests for find_entry_worker_path function."""

    def test_main_at_project_root(self, tmp_path):
        """Test finding main.worker at project root."""
        (tmp_path / "main.worker").write_text("---\nname: main\n---\n")

        path = find_entry_worker_path(tmp_path, "main")
        assert path == tmp_path / "main.worker"

    def test_main_in_workers_directory(self, tmp_path):
        """Test finding main.worker in workers/ directory."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "main.worker").write_text("---\nname: main\n---\n")

        path = find_entry_worker_path(tmp_path, "main")
        assert path == workers_dir / "main.worker"

    def test_main_at_root_takes_precedence(self, tmp_path):
        """Test that main.worker at root takes precedence over workers/."""
        (tmp_path / "main.worker").write_text("---\nname: main\n---\nRoot main")

        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "main.worker").write_text("---\nname: main\n---\nWorkers main")

        path = find_entry_worker_path(tmp_path, "main")
        assert path == tmp_path / "main.worker"

    def test_custom_entry_in_workers(self, tmp_path):
        """Test finding custom entry worker in workers/."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "custom.worker").write_text("---\nname: custom\n---\n")

        path = find_entry_worker_path(tmp_path, "custom")
        assert path == workers_dir / "custom.worker"

    def test_directory_form_worker(self, tmp_path):
        """Test finding directory-form worker."""
        worker_dir = tmp_path / "workers" / "complex"
        worker_dir.mkdir(parents=True)
        (worker_dir / "worker.worker").write_text("---\nname: complex\n---\n")

        path = find_entry_worker_path(tmp_path, "complex")
        assert path == worker_dir / "worker.worker"

    def test_entry_not_found_raises(self, tmp_path):
        """Test that missing entry worker raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            find_entry_worker_path(tmp_path, "nonexistent")

        assert "Entry worker 'nonexistent' not found" in str(exc_info.value)


class TestProjectContext:
    """Tests for ProjectContext dataclass."""

    def test_workers_dir_property(self, tmp_path):
        """Test workers_dir property."""
        context = ProjectContext(
            project_root=tmp_path,
            config=ProjectConfig(),
            entry_worker="main",
        )
        assert context.workers_dir == tmp_path / "workers"

    def test_templates_dir_property(self, tmp_path):
        """Test templates_dir property."""
        context = ProjectContext(
            project_root=tmp_path,
            config=ProjectConfig(),
            entry_worker="main",
        )
        assert context.templates_dir == tmp_path / "templates"

    def test_tools_path_with_tools_py(self, tmp_path):
        """Test tools_path property with tools.py file."""
        (tmp_path / "tools.py").write_text("# tools")

        context = ProjectContext(
            project_root=tmp_path,
            config=ProjectConfig(),
            entry_worker="main",
        )
        assert context.tools_path == tmp_path / "tools.py"

    def test_tools_path_with_tools_package(self, tmp_path):
        """Test tools_path property with tools/ package."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "__init__.py").write_text("# tools package")

        context = ProjectContext(
            project_root=tmp_path,
            config=ProjectConfig(),
            entry_worker="main",
        )
        assert context.tools_path == tools_dir

    def test_tools_path_none_when_missing(self, tmp_path):
        """Test tools_path property when no tools exist."""
        context = ProjectContext(
            project_root=tmp_path,
            config=ProjectConfig(),
            entry_worker="main",
        )
        assert context.tools_path is None


class TestRegistryProjectConfigInheritance:
    """Tests for project config inheritance in WorkerRegistry."""

    def test_registry_without_project_config(self, tmp_path):
        """Test that registry works without project config."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\nmodel: openai:gpt-4o\n---\nTest worker"
        )

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("test")

        assert definition.name == "test"
        assert definition.model == "openai:gpt-4o"

    def test_registry_inherits_project_model(self, tmp_path):
        """Test that worker inherits model from project config."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\n---\nTest worker"
        )

        project_config = ProjectConfig(model="anthropic:claude-haiku-4-5")
        registry = WorkerRegistry(tmp_path, project_config=project_config)
        definition = registry.load_definition("test")

        assert definition.model == "anthropic:claude-haiku-4-5"

    def test_worker_model_overrides_project(self, tmp_path):
        """Test that worker's own model overrides project config."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\nmodel: openai:gpt-4o\n---\nTest worker"
        )

        project_config = ProjectConfig(model="anthropic:claude-haiku-4-5")
        registry = WorkerRegistry(tmp_path, project_config=project_config)
        definition = registry.load_definition("test")

        assert definition.model == "openai:gpt-4o"

    def test_registry_merges_toolsets(self, tmp_path):
        """Test that toolsets are deep merged (project + worker)."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\ntoolsets:\n  custom:\n    tools:\n      my_tool: {}\n---\n"
        )

        project_config = ProjectConfig(
            toolsets={"filesystem": {}, "shell": {"rules": []}}
        )
        registry = WorkerRegistry(tmp_path, project_config=project_config)
        definition = registry.load_definition("test")

        # Should have all three toolsets
        assert "filesystem" in definition.toolsets
        assert "shell" in definition.toolsets
        assert "custom" in definition.toolsets

    def test_worker_toolsets_override_project(self, tmp_path):
        """Test that worker's toolset config overrides project's same-named toolset."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\ntoolsets:\n  shell:\n    rules:\n      - pattern: echo\n---\n"
        )

        project_config = ProjectConfig(
            toolsets={"shell": {"rules": []}}
        )
        registry = WorkerRegistry(tmp_path, project_config=project_config)
        definition = registry.load_definition("test")

        # Worker's shell config should override
        assert definition.toolsets["shell"]["rules"] == [{"pattern": "echo"}]

    def test_registry_merges_sandbox_paths(self, tmp_path):
        """Test that sandbox paths are deep merged."""
        workers_dir = tmp_path / "workers"
        workers_dir.mkdir()
        (workers_dir / "test.worker").write_text(
            "---\nname: test\nsandbox:\n  paths:\n    scratch:\n      root: ./scratch\n      mode: rw\n---\n"
        )

        project_config = ProjectConfig(
            sandbox=SandboxConfig(
                paths={
                    "input": PathConfig(root="./input", mode="ro"),
                    "output": PathConfig(root="./output", mode="rw"),
                }
            )
        )
        registry = WorkerRegistry(tmp_path, project_config=project_config)
        definition = registry.load_definition("test")

        # Should have all three paths
        assert "input" in definition.sandbox.paths
        assert "output" in definition.sandbox.paths
        assert "scratch" in definition.sandbox.paths

    def test_main_worker_at_project_root(self, tmp_path):
        """Test that main.worker at project root is found."""
        (tmp_path / "main.worker").write_text(
            "---\nname: main\n---\nMain entry point"
        )

        registry = WorkerRegistry(tmp_path)
        definition = registry.load_definition("main")

        assert definition.name == "main"
        assert definition.instructions == "Main entry point"


class TestProjectConfigToCreationDefaults:
    """Tests for ProjectConfig.to_creation_defaults method."""

    def test_converts_to_creation_defaults(self):
        """Test conversion to WorkerCreationDefaults."""
        config = ProjectConfig(
            model="anthropic:claude-haiku-4-5",
            toolsets={"filesystem": {}},
            sandbox=SandboxConfig(
                paths={"data": PathConfig(root="./data", mode="rw")}
            ),
        )

        defaults = config.to_creation_defaults()

        assert defaults.default_model == "anthropic:claude-haiku-4-5"
        assert defaults.default_toolsets == {"filesystem": {}}
        assert defaults.default_sandbox is not None
        assert "data" in defaults.default_sandbox.paths
