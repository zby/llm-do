"""Tests for manifest schema and loader."""

import json

import pytest

from llm_do.runtime.manifest import (
    EntryConfig,
    ProjectManifest,
    RuntimeConfig,
    load_manifest,
    resolve_manifest_paths,
)


class TestRuntimeConfig:
    """Tests for RuntimeConfig schema."""

    def test_defaults(self):
        """Test default values."""
        config = RuntimeConfig()
        assert config.approval_mode == "prompt"
        assert config.max_depth == 5
        assert config.model is None
        assert config.return_permission_errors is False

    def test_approval_modes(self):
        """Test valid approval modes."""
        for mode in ("prompt", "approve_all", "reject_all"):
            config = RuntimeConfig(approval_mode=mode)
            assert config.approval_mode == mode

    def test_invalid_approval_mode(self):
        """Test invalid approval mode raises error."""
        with pytest.raises(ValueError):
            RuntimeConfig(approval_mode="invalid")

    def test_max_depth_minimum(self):
        """Test max_depth must be >= 1."""
        with pytest.raises(ValueError):
            RuntimeConfig(max_depth=0)

    def test_extra_fields_forbidden(self):
        """Test extra fields raise error."""
        with pytest.raises(ValueError):
            RuntimeConfig(unknown_field="value")


class TestEntryConfig:
    """Tests for EntryConfig schema."""

    def test_name_required(self):
        """Test name is required."""
        with pytest.raises(ValueError):
            EntryConfig()

    def test_name_non_empty(self):
        """Test name must be non-empty."""
        with pytest.raises(ValueError):
            EntryConfig(name="")

    def test_valid_entry(self):
        """Test valid entry config."""
        entry = EntryConfig(name="main")
        assert entry.name == "main"
        assert entry.model is None
        assert entry.input is None

    def test_with_model_and_input(self):
        """Test entry with model and input."""
        entry = EntryConfig(
            name="main",
            model="gpt-4",
            input={"input": "Hello"},
        )
        assert entry.model == "gpt-4"
        assert entry.input == {"input": "Hello"}


class TestProjectManifest:
    """Tests for ProjectManifest schema."""

    def test_minimal_valid_manifest(self):
        """Test minimal valid manifest."""
        manifest = ProjectManifest(
            version=1,
            runtime=RuntimeConfig(),
            entry=EntryConfig(name="main"),
            worker_files=["main.worker"],
        )
        assert manifest.version == 1
        assert manifest.allow_cli_input is True

    def test_version_required(self):
        """Test version is required."""
        with pytest.raises(ValueError):
            ProjectManifest(
                runtime=RuntimeConfig(),
                entry=EntryConfig(name="main"),
                worker_files=["main.worker"],
            )

    def test_unsupported_version(self):
        """Test unsupported version raises error."""
        with pytest.raises(ValueError, match="Unsupported manifest version"):
            ProjectManifest(
                version=2,
                runtime=RuntimeConfig(),
                entry=EntryConfig(name="main"),
                worker_files=["main.worker"],
            )

    def test_runtime_required(self):
        """Test runtime is required."""
        with pytest.raises(ValueError):
            ProjectManifest(
                version=1,
                entry=EntryConfig(name="main"),
                worker_files=["main.worker"],
            )

    def test_entry_required(self):
        """Test entry is required."""
        with pytest.raises(ValueError):
            ProjectManifest(
                version=1,
                runtime=RuntimeConfig(),
                worker_files=["main.worker"],
            )

    def test_requires_at_least_one_file(self):
        """Test at least one worker_files or python_files required."""
        with pytest.raises(ValueError, match="At least one"):
            ProjectManifest(
                version=1,
                runtime=RuntimeConfig(),
                entry=EntryConfig(name="main"),
            )

    def test_empty_file_path_rejected(self):
        """Test empty file paths are rejected."""
        with pytest.raises(ValueError, match="non-empty"):
            ProjectManifest(
                version=1,
                runtime=RuntimeConfig(),
                entry=EntryConfig(name="main"),
                worker_files=[""],
            )

    def test_duplicate_file_paths_rejected(self):
        """Test duplicate file paths are rejected."""
        with pytest.raises(ValueError, match="Duplicate"):
            ProjectManifest(
                version=1,
                runtime=RuntimeConfig(),
                entry=EntryConfig(name="main"),
                worker_files=["main.worker", "main.worker"],
            )

    def test_allow_cli_input_default_true(self):
        """Test allow_cli_input defaults to true."""
        manifest = ProjectManifest(
            version=1,
            runtime=RuntimeConfig(),
            entry=EntryConfig(name="main"),
            python_files=["tools.py"],
        )
        assert manifest.allow_cli_input is True

    def test_allow_cli_input_false(self):
        """Test allow_cli_input can be set false."""
        manifest = ProjectManifest(
            version=1,
            runtime=RuntimeConfig(),
            entry=EntryConfig(name="main"),
            allow_cli_input=False,
            python_files=["tools.py"],
        )
        assert manifest.allow_cli_input is False

    def test_extra_fields_forbidden(self):
        """Test extra fields raise error."""
        with pytest.raises(ValueError):
            ProjectManifest(
                version=1,
                runtime=RuntimeConfig(),
                entry=EntryConfig(name="main"),
                worker_files=["main.worker"],
                unknown_field="value",
            )


class TestLoadManifest:
    """Tests for load_manifest function."""

    def test_load_valid_manifest(self, tmp_path):
        """Test loading a valid manifest file."""
        manifest_data = {
            "version": 1,
            "runtime": {"approval_mode": "approve_all", "max_depth": 3},
            "entry": {"name": "main"},
            "worker_files": ["main.worker"],
        }
        manifest_file = tmp_path / "project.json"
        manifest_file.write_text(json.dumps(manifest_data))

        manifest, manifest_dir = load_manifest(manifest_file)

        assert manifest.version == 1
        assert manifest.runtime.approval_mode == "approve_all"
        assert manifest.runtime.max_depth == 3
        assert manifest.entry.name == "main"
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


class TestResolveManifestPaths:
    """Tests for resolve_manifest_paths function."""

    def test_resolve_existing_files(self, tmp_path):
        """Test resolving existing file paths."""
        # Create test files
        worker = tmp_path / "main.worker"
        worker.write_text("---\nname: main\n---\nTest")
        python = tmp_path / "tools.py"
        python.write_text("# tools")

        manifest = ProjectManifest(
            version=1,
            runtime=RuntimeConfig(),
            entry=EntryConfig(name="main"),
            worker_files=["main.worker"],
            python_files=["tools.py"],
        )

        worker_paths, python_paths = resolve_manifest_paths(manifest, tmp_path)

        assert len(worker_paths) == 1
        assert len(python_paths) == 1
        assert worker_paths[0] == worker.resolve()
        assert python_paths[0] == python.resolve()

    def test_worker_file_not_found(self, tmp_path):
        """Test missing worker file raises FileNotFoundError."""
        manifest = ProjectManifest(
            version=1,
            runtime=RuntimeConfig(),
            entry=EntryConfig(name="main"),
            worker_files=["missing.worker"],
        )

        with pytest.raises(FileNotFoundError, match="Worker file not found"):
            resolve_manifest_paths(manifest, tmp_path)

    def test_python_file_not_found(self, tmp_path):
        """Test missing python file raises FileNotFoundError."""
        manifest = ProjectManifest(
            version=1,
            runtime=RuntimeConfig(),
            entry=EntryConfig(name="main"),
            python_files=["missing.py"],
        )

        with pytest.raises(FileNotFoundError, match="Python file not found"):
            resolve_manifest_paths(manifest, tmp_path)

    def test_relative_path_resolution(self, tmp_path):
        """Test paths are resolved relative to manifest directory."""
        # Create nested directory structure
        subdir = tmp_path / "workers"
        subdir.mkdir()
        worker = subdir / "main.worker"
        worker.write_text("---\nname: main\n---\nTest")

        manifest = ProjectManifest(
            version=1,
            runtime=RuntimeConfig(),
            entry=EntryConfig(name="main"),
            worker_files=["workers/main.worker"],
        )

        worker_paths, _ = resolve_manifest_paths(manifest, tmp_path)

        assert worker_paths[0] == worker.resolve()
