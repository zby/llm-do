import textwrap

from llm_do.config import load_config


# TRIVIAL: mirrors dataclass defaults; kept for documentation.
def test_load_config_defaults_when_missing(tmp_path):
    config = load_config(tmp_path)

    assert config.path is None
    assert config.workflow.spec_file is None
    assert config.model.allowed_models == []
    assert config.requires_attachment_types == []


def test_load_config_reads_fields(tmp_path):
    config_file = tmp_path / "llm-do.toml"
    config_file.write_text(
        textwrap.dedent(
            """
            [workflow]
            spec = "SPEC.md"

            [model]
            allowed_models = ["allowed-model"]
            required_attachment_types = ["application/pdf"]

            [prompt]
            template = "my-template"

            [prompt.params]
            spec_title = "Pitchdeck"
            """
        ).strip()
    )

    config = load_config(tmp_path)

    assert config.path == config_file
    assert config.workflow.spec_file == "SPEC.md"
    assert config.model.allowed_models == ["allowed-model"]
    assert config.requires_attachment_types == ["application/pdf"]
    assert config.prompt.template == "my-template"
    assert config.prompt.params["spec_title"] == "Pitchdeck"
