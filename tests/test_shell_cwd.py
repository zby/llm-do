"""Tests for shell_cwd resolution and behavior."""
from pathlib import Path

import pytest

from llm_do import ApprovalController, WorkerDefinition, WorkerRegistry, WorkerCreationDefaults
from llm_do.runtime import _prepare_worker_context


def test_shell_cwd_none_by_default(tmp_path):
    """Test that shell_cwd is None when not specified in worker definition."""
    worker_def = WorkerDefinition(
        name="test_worker",
        instructions="Test worker",
        model="test:mock",
    )

    registry = WorkerRegistry(tmp_path)
    registry.save_definition(worker_def)

    prep = _prepare_worker_context(
        registry=registry,
        worker="test_worker",
        input_data="test",
        attachments=None,
        caller_effective_model=None,
        cli_model=None,
        creation_defaults=WorkerCreationDefaults(),
        approval_controller=ApprovalController(mode="approve_all"),
        message_callback=None,
    )

    # shell_cwd should be None (will default to Path.cwd() in shell tool)
    assert prep.context.shell_cwd is None


def test_shell_cwd_resolves_relative_path(tmp_path):
    """Test that relative shell_cwd is resolved relative to registry root."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()

    worker_def = WorkerDefinition(
        name="test_worker",
        instructions="Test worker",
        model="test:mock",
        shell_cwd="subdir",  # Relative path
    )

    registry = WorkerRegistry(registry_dir)
    registry.save_definition(worker_def)

    prep = _prepare_worker_context(
        registry=registry,
        worker="test_worker",
        input_data="test",
        attachments=None,
        caller_effective_model=None,
        cli_model=None,
        creation_defaults=WorkerCreationDefaults(),
        approval_controller=ApprovalController(mode="approve_all"),
        message_callback=None,
    )

    # shell_cwd should be resolved to registry_dir/subdir
    expected = (registry_dir / "subdir").resolve()
    assert prep.context.shell_cwd == expected


def test_shell_cwd_accepts_absolute_path(tmp_path):
    """Test that absolute shell_cwd is used as-is."""
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    worker_def = WorkerDefinition(
        name="test_worker",
        instructions="Test worker",
        model="test:mock",
        shell_cwd=str(target_dir),  # Absolute path
    )

    registry = WorkerRegistry(tmp_path / "registry")
    registry.save_definition(worker_def)

    prep = _prepare_worker_context(
        registry=registry,
        worker="test_worker",
        input_data="test",
        attachments=None,
        caller_effective_model=None,
        cli_model=None,
        creation_defaults=WorkerCreationDefaults(),
        approval_controller=ApprovalController(mode="approve_all"),
        message_callback=None,
    )

    # shell_cwd should be the absolute path
    assert prep.context.shell_cwd == target_dir


def test_shell_cwd_can_be_overridden_via_set(tmp_path):
    """Test that shell_cwd can be overridden using --set."""
    from llm_do.config_overrides import apply_cli_overrides

    target_dir = tmp_path / "override_target"
    target_dir.mkdir()

    # Worker without shell_cwd
    worker_def = WorkerDefinition(
        name="test_worker",
        instructions="Test worker",
        model="test:mock",
    )

    # Apply override
    overridden = apply_cli_overrides(
        worker_def,
        set_overrides=[f"shell_cwd={target_dir}"]
    )

    assert overridden.shell_cwd == str(target_dir)

    # Verify it resolves correctly
    registry = WorkerRegistry(tmp_path / "registry")
    registry.save_definition(overridden)

    prep = _prepare_worker_context(
        registry=registry,
        worker="test_worker",
        input_data="test",
        attachments=None,
        caller_effective_model=None,
        cli_model=None,
        creation_defaults=WorkerCreationDefaults(),
        approval_controller=ApprovalController(mode="approve_all"),
        message_callback=None,
    )

    # Should use the overridden absolute path
    assert prep.context.shell_cwd == target_dir


def test_shell_cwd_dot_means_current_directory(tmp_path):
    """Test that shell_cwd='.' resolves to current directory at runtime."""
    from llm_do.config_overrides import apply_cli_overrides

    worker_def = WorkerDefinition(
        name="test_worker",
        instructions="Test worker",
        model="test:mock",
    )

    # Override with '.' (current directory)
    overridden = apply_cli_overrides(
        worker_def,
        set_overrides=["shell_cwd=."]
    )

    assert overridden.shell_cwd == "."

    # When resolved relative to registry root, it becomes registry root
    registry = WorkerRegistry(tmp_path / "registry")
    registry.save_definition(overridden)

    prep = _prepare_worker_context(
        registry=registry,
        worker="test_worker",
        input_data="test",
        attachments=None,
        caller_effective_model=None,
        cli_model=None,
        creation_defaults=WorkerCreationDefaults(),
        approval_controller=ApprovalController(mode="approve_all"),
        message_callback=None,
    )

    # '.' resolves to registry root
    expected = (tmp_path / "registry").resolve()
    assert prep.context.shell_cwd == expected
