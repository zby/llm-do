import pytest

from llm_do.config import LlmDoConfig, ModelConstraints, PromptSettings
from llm_do.executor import _build_prompt_and_system, _enforce_model_constraints


class DummyModel:
    def __init__(self, model_id="allowed", attachment_types=None, model_name=None):
        self.model_id = model_id
        self.model_name = model_name
        self.attachment_types = attachment_types or set()


# TRIVIAL: sanity-checks the allowlist pass-through.
def test_enforce_model_constraints_allows_configured_model():
    config = LlmDoConfig(model=ModelConstraints(allowed_models=["allowed"]))
    model = DummyModel(model_id="allowed")

    _enforce_model_constraints(model, "allowed", config)


def test_enforce_model_constraints_rejects_missing_capability():
    config = LlmDoConfig(model=ModelConstraints(required_attachment_types=["application/pdf"]))
    model = DummyModel(model_id="allowed", attachment_types={"text/plain"})

    with pytest.raises(Exception) as excinfo:
        _enforce_model_constraints(model, "allowed", config)

    assert "application/pdf" in str(excinfo.value)


# TRIVIAL: ensures default passthrough without template logic.
def test_build_prompt_and_system_without_template(tmp_path):
    config = LlmDoConfig()
    prompt, system = _build_prompt_and_system(
        task="process", spec_content="spec", spec_file=tmp_path / "SPEC.md", config=config, working_dir=None
    )

    assert prompt == "process"
    assert system == "spec"


def test_build_prompt_and_system_with_template(tmp_path):
    template_file = tmp_path / "template.yaml"
    template_file.write_text(
        """name: pitchdeck
prompt: "Task: ${task} (${extra})"
system: |
  SpecPath=${spec_path}
  Spec=${spec}
"""
    )
    config = LlmDoConfig(
        prompt=PromptSettings(
            template=str(template_file),
            params={"extra": "details"},
        )
    )

    prompt, system = _build_prompt_and_system(
        task="process",
        spec_content="## SPEC",
        spec_file=tmp_path / "SPEC.md",
        config=config,
        working_dir=tmp_path,
    )

    assert prompt == "Task: process (details)"
    assert "Spec=## SPEC" in system
    assert str(tmp_path / "SPEC.md") in system


def test_build_prompt_and_system_errors_on_missing_template_vars(tmp_path):
    template_file = tmp_path / "template.yaml"
    template_file.write_text(
        """name: invalid
prompt: "${missing}"
"""
    )
    config = LlmDoConfig(prompt=PromptSettings(template=str(template_file)))

    with pytest.raises(Exception) as excinfo:
        _build_prompt_and_system(
            task="task",
            spec_content="spec",
            spec_file=tmp_path / "SPEC.md",
            config=config,
            working_dir=None,
        )

    assert "missing" in str(excinfo.value)
