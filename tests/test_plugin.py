import click
import pytest

from llm_do.config import LlmDoConfig, WorkflowSettings
from llm_do.plugin import _discover_spec_path


def test_discover_spec_requires_config(tmp_path):
    config = LlmDoConfig()

    with pytest.raises(click.ClickException) as excinfo:
        _discover_spec_path(tmp_path, config)

    assert "No llm-do config" in str(excinfo.value)


def test_discover_spec_requires_spec_entry(tmp_path):
    config_path = tmp_path / "llm-do.toml"
    config_path.write_text("[model]\n")
    config = LlmDoConfig(path=config_path)

    with pytest.raises(click.ClickException) as excinfo:
        _discover_spec_path(tmp_path, config)

    assert "missing [workflow].spec" in str(excinfo.value)


# TRIVIAL: confirms happy-path string resolution.
def test_discover_spec_returns_configured_path(tmp_path):
    spec_file = tmp_path / "SPEC.md"
    spec_file.write_text("content")
    config_path = tmp_path / "llm-do.toml"
    config = LlmDoConfig(path=config_path, workflow=WorkflowSettings(spec_file="SPEC.md"))

    resolved = _discover_spec_path(tmp_path, config)

    assert resolved == str(spec_file)


def test_discover_spec_errors_if_missing_file(tmp_path):
    config_path = tmp_path / "llm-do.toml"
    config = LlmDoConfig(path=config_path, workflow=WorkflowSettings(spec_file="SPEC.md"))

    with pytest.raises(click.ClickException) as excinfo:
        _discover_spec_path(tmp_path, config)

    assert "not found" in str(excinfo.value)
