import click
import pytest

from llm_do.context import WorkflowContext


class DummyModel:
    def __init__(self, *, model_id="allowed", attachment_types=None, model_name=None):
        self.model_id = model_id
        self.model_name = model_name
        self.attachment_types = attachment_types or set()


def write_config(tmp_path, body: str):
    config_path = tmp_path / "llm-do.toml"
    config_path.write_text(body.strip())
    return config_path


def test_context_requires_spec_without_config(tmp_path):
    with pytest.raises(click.ClickException):
        WorkflowContext(tmp_path)


def test_context_requires_spec_entry(tmp_path):
    write_config(tmp_path, "[model]\n")

    with pytest.raises(click.ClickException) as excinfo:
        WorkflowContext(tmp_path)

    assert "missing [workflow].spec" in str(excinfo.value)


def test_context_errors_if_spec_missing(tmp_path):
    write_config(tmp_path, "[workflow]\nspec = \"SPEC.md\"")

    with pytest.raises(click.ClickException) as excinfo:
        WorkflowContext(tmp_path)

    assert "Spec file not found" in str(excinfo.value)


def test_context_uses_config_spec(tmp_path):
    spec = tmp_path / "SPEC.md"
    spec.write_text("spec")
    write_config(tmp_path, "[workflow]\nspec = \"SPEC.md\"")

    ctx = WorkflowContext(tmp_path)

    assert ctx.spec_path == spec.resolve()
    assert ctx.spec_text == "spec"


def test_context_uses_cli_spec_override(tmp_path):
    spec = tmp_path / "custom.md"
    spec.write_text("cli spec")

    ctx = WorkflowContext(tmp_path, spec_path=str(spec))

    assert ctx.spec_path == spec.resolve()
    assert ctx.spec_text == "cli spec"


def test_context_builds_prompt_with_template(tmp_path):
    spec = tmp_path / "SPEC.md"
    spec.write_text("SPEC CONTENT")
    template = tmp_path / "template.yaml"
    template.write_text(
        """name: pitchdeck
prompt: "Task: ${task} (${extra})"
system: |
  SpecPath=${spec_path}
  Spec=${spec}
"""
    )
    write_config(
        tmp_path,
        f"""
        [workflow]
        spec = "SPEC.md"

        [prompt]
        template = "{template}"

        [prompt.params]
        extra = "details"
        """
    )

    ctx = WorkflowContext(tmp_path)

    prompt, system = ctx.build_prompt("process")

    assert prompt == "Task: process (details)"
    assert "SpecPath=" in system and str(spec) in system
    assert "Spec=SPEC CONTENT" in system


def test_context_enforces_allowed_models(tmp_path):
    spec = tmp_path / "SPEC.md"
    spec.write_text("spec")
    write_config(
        tmp_path,
        """
        [workflow]
        spec = "SPEC.md"

        [model]
        allowed_models = ["allowed", "alias"]
        """
    )
    ctx = WorkflowContext(tmp_path)
    allowed_model = DummyModel(model_id="allowed")
    ctx.ensure_model_allowed(allowed_model, "allowed")

    disallowed = DummyModel(model_id="other")
    with pytest.raises(Exception):
        ctx.ensure_model_allowed(disallowed, "other")


def test_context_enforces_attachment_requirements(tmp_path):
    spec = tmp_path / "SPEC.md"
    spec.write_text("spec")
    write_config(
        tmp_path,
        """
        [workflow]
        spec = "SPEC.md"

        [model]
        required_attachment_types = ["application/pdf"]
        """
    )
    ctx = WorkflowContext(tmp_path)

    ok_model = DummyModel(attachment_types={"application/pdf"})
    ctx.ensure_model_allowed(ok_model, "model")

    bad_model = DummyModel(attachment_types={"text/plain"})
    with pytest.raises(Exception):
        ctx.ensure_model_allowed(bad_model, "model")
