"""Tests for manifest schema and loader."""

import json

import pytest

from llm_do.runtime.manifest import (
    EntryConfig,
    ManifestRuntimeConfig,
    ProjectManifest,
    load_manifest,
    resolve_generated_agents_dir,
    resolve_manifest_paths,
)


class TestManifestRuntimeConfig:
    """Tests for ManifestRuntimeConfig schema."""

    def test_defaults(self):
        """Test default values."""
        config = ManifestRuntimeConfig()
        assert config.approval_mode == "prompt"
        assert config.max_depth == 5
        assert config.return_permission_errors is False
        assert config.agent_calls_require_approval is False
        assert config.agent_attachments_require_approval is False
        assert config.agent_approval_overrides == {}

    def test_approval_modes(self):
        """Test valid approval modes."""
        for mode in ("prompt", "approve_all", "reject_all"):
            config = ManifestRuntimeConfig(approval_mode=mode)
            assert config.approval_mode == mode

    def test_invalid_approval_mode(self):
        """Test invalid approval mode raises error."""
        with pytest.raises(ValueError):
            ManifestRuntimeConfig(approval_mode="invalid")

    def test_max_depth_minimum(self):
        """Test max_depth must be >= 1."""
        with pytest.raises(ValueError):
            ManifestRuntimeConfig(max_depth=0)

    def test_extra_fields_forbidden(self):
        """Test extra fields raise error."""
        with pytest.raises(ValueError):
            ManifestRuntimeConfig(unknown_field="value")

    def test_agent_approval_overrides_reject_extra_fields(self):
        """Per-agent overrides should forbid unknown fields."""
        with pytest.raises(ValueError):
            ManifestRuntimeConfig(
                agent_approval_overrides={
                    "summarizer": {"unexpected": True},
                }
            )

    def test_model_field_rejected(self):
        """Test model field is not allowed."""
        with pytest.raises(ValueError):
            ManifestRuntimeConfig(model="gpt-4")


class TestEntryConfig:
    """Tests for EntryConfig schema."""

    def test_requires_target(self):
        """Test agent or function is required."""
        with pytest.raises(ValueError):
            EntryConfig()

    def test_with_args(self):
        """Test entry with args."""
        entry = EntryConfig(
            agent="main",
            args={"input": "Hello"},
        )
        assert entry.agent == "main"
        assert entry.args == {"input": "Hello"}

    def test_function_entry(self):
        """Test entry with function."""
        entry = EntryConfig(
            function="tools.py:main",
            args={"input": "Hello"},
        )
        assert entry.function == "tools.py:main"

    def test_rejects_multiple_targets(self):
        """Test both agent and function set raises error."""
        with pytest.raises(ValueError):
            EntryConfig(agent="main", function="tools.py:main")

    def test_model_field_rejected(self):
        """Test model field is not allowed."""
        with pytest.raises(ValueError):
            EntryConfig(agent="main", model="gpt-4")


class TestProjectManifest:
    """Tests for ProjectManifest schema."""

    def test_minimal_valid_manifest(self):
        """Test minimal valid manifest."""
        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            agent_files=["main.agent"],
        )
        assert manifest.version == 1
        assert manifest.allow_cli_input is True

    def test_version_required(self):
        """Test version is required."""
        with pytest.raises(ValueError):
            ProjectManifest(
                runtime=ManifestRuntimeConfig(),
                entry=EntryConfig(agent="main"),
                agent_files=["main.agent"],
            )

    def test_unsupported_version(self):
        """Test unsupported version raises error."""
        with pytest.raises(ValueError, match="Unsupported manifest version"):
            ProjectManifest(
                version=2,
                runtime=ManifestRuntimeConfig(),
                entry=EntryConfig(agent="main"),
                agent_files=["main.agent"],
            )

    def test_runtime_required(self):
        """Test runtime is required."""
        with pytest.raises(ValueError):
            ProjectManifest(
                version=1,
                entry=EntryConfig(agent="main"),
                agent_files=["main.agent"],
            )

    def test_entry_required(self):
        """Test entry is required."""
        with pytest.raises(ValueError):
            ProjectManifest(
                version=1,
                runtime=ManifestRuntimeConfig(),
                agent_files=["main.agent"],
            )

    def test_requires_at_least_one_file(self):
        """Test at least one agent_files or python_files required."""
        with pytest.raises(ValueError, match="At least one"):
            ProjectManifest(
                version=1,
                runtime=ManifestRuntimeConfig(),
                entry=EntryConfig(agent="main"),
            )

    def test_empty_file_path_rejected(self):
        """Test empty file paths are rejected."""
        with pytest.raises(ValueError, match="non-empty"):
            ProjectManifest(
                version=1,
                runtime=ManifestRuntimeConfig(),
                entry=EntryConfig(agent="main"),
                agent_files=[""],
            )

    def test_duplicate_file_paths_rejected(self):
        """Test duplicate file paths are rejected."""
        with pytest.raises(ValueError, match="Duplicate"):
            ProjectManifest(
                version=1,
                runtime=ManifestRuntimeConfig(),
                entry=EntryConfig(agent="main"),
                agent_files=["main.agent", "main.agent"],
            )

    def test_allow_cli_input_default_true(self):
        """Test allow_cli_input defaults to true."""
        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            python_files=["tools.py"],
        )
        assert manifest.allow_cli_input is True

    def test_allow_cli_input_false(self):
        """Test allow_cli_input can be set false."""
        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            allow_cli_input=False,
            python_files=["tools.py"],
        )
        assert manifest.allow_cli_input is False

    def test_extra_fields_forbidden(self):
        """Test extra fields raise error."""
        with pytest.raises(ValueError):
            ProjectManifest(
                version=1,
                runtime=ManifestRuntimeConfig(),
                entry=EntryConfig(agent="main"),
                agent_files=["main.agent"],
                unknown_field="value",
            )


class TestLoadManifest:
    """Tests for load_manifest function."""

    def test_load_valid_manifest(self, tmp_path):
        """Test loading a valid manifest file."""
        manifest_data = {
            "version": 1,
            "runtime": {"approval_mode": "approve_all", "max_depth": 3},
            "entry": {"agent": "main"},
            "agent_files": ["main.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        manifest, manifest_dir = load_manifest(manifest_file)

        assert manifest.version == 1
        assert manifest.runtime.approval_mode == "approve_all"
        assert manifest.runtime.max_depth == 3
        assert manifest_dir == tmp_path

    def test_file_not_found(self, tmp_path):
        """Test loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "nonexistent.json")

    def test_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises ValueError."""
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text("not valid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_manifest(manifest_file)

    def test_invalid_manifest_schema(self, tmp_path):
        """Test invalid manifest schema raises ValueError."""
        manifest_data = {"version": 1}  # Missing required fields
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        with pytest.raises(ValueError, match="Invalid manifest"):
            load_manifest(manifest_file)

    def test_load_from_directory(self, tmp_path):
        """Test loading manifest by specifying directory path."""
        manifest_data = {
            "version": 1,
            "runtime": {"approval_mode": "approve_all"},
            "entry": {"agent": "main"},
            "agent_files": ["main.agent"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        # Pass directory instead of file path
        manifest, manifest_dir = load_manifest(tmp_path)

        assert manifest.version == 1
        assert manifest.runtime.approval_mode == "approve_all"
        assert manifest_dir == tmp_path

    def test_directory_without_project_json(self, tmp_path):
        """Test loading from directory without project.json raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="project.json"):
            load_manifest(tmp_path)


class TestResolveManifestPaths:
    """Tests for resolve_manifest_paths function."""

    def test_resolve_existing_files(self, tmp_path):
        """Test resolving existing file paths."""
        # Create test files
        agent = tmp_path / "main.agent"
        agent.write_text("---\nname: main\n---\nTest")
        python = tmp_path / "tools.py"
        python.write_text("# tools")

        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            agent_files=["main.agent"],
            python_files=["tools.py"],
        )

        agent_paths, python_paths = resolve_manifest_paths(manifest, tmp_path)

        assert len(agent_paths) == 1
        assert len(python_paths) == 1
        assert agent_paths[0] == agent.resolve()

    def test_agent_file_not_found(self, tmp_path):
        """Test missing agent file raises FileNotFoundError."""
        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            agent_files=["missing.agent"],
        )

        with pytest.raises(FileNotFoundError, match="Agent file not found"):
            resolve_manifest_paths(manifest, tmp_path)

    def test_python_file_not_found(self, tmp_path):
        """Test missing python file raises FileNotFoundError."""
        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            python_files=["missing.py"],
        )

        with pytest.raises(FileNotFoundError, match="Python file not found"):
            resolve_manifest_paths(manifest, tmp_path)

    def test_relative_path_resolution(self, tmp_path):
        """Test paths are resolved relative to manifest directory."""
        # Create nested directory structure
        subdir = tmp_path / "agents"
        subdir.mkdir()
        agent = subdir / "main.agent"
        agent.write_text("---\nname: main\n---\nTest")

        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            agent_files=["agents/main.agent"],
        )

        agent_paths, _ = resolve_manifest_paths(manifest, tmp_path)

        assert agent_paths[0] == agent.resolve()


class TestResolveGeneratedAgentsDir:
    """Tests for resolve_generated_agents_dir function."""

    def test_none_returns_none(self, tmp_path):
        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            agent_files=["main.agent"],
        )
        assert resolve_generated_agents_dir(manifest, tmp_path) is None

    def test_relative_path_resolves(self, tmp_path):
        manifest = ProjectManifest(
            version=1,
            runtime=ManifestRuntimeConfig(),
            entry=EntryConfig(agent="main"),
            agent_files=["main.agent"],
            generated_agents_dir="generated",
        )
        resolved = resolve_generated_agents_dir(manifest, tmp_path)
        assert resolved == (tmp_path / "generated").resolve()
