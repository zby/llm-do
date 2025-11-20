from __future__ import annotations

import json
import pytest

from llm_do.tools_template_call import TemplateCall


def test_template_call_executes(dummy_model, sample_template, sample_attachment):
    tool = TemplateCall(
        allow_templates=[str(sample_template)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
    )
    result = tool.run(
        template=str(sample_template),
        input="process",
        attachments=[str(sample_attachment)],
        fragments=["procedure"],
        expect_json=True,
    )
    assert json.loads(result) == {"message": "ok"}
    assert dummy_model.calls
    prompt_text, kwargs = dummy_model.calls[0]
    assert "attachments" in kwargs and len(kwargs["attachments"]) == 1
    assert kwargs["fragments"] == ["procedure"]
    assert kwargs["schema"] == {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }


def test_disallowed_template_raises(sample_template):
    tool = TemplateCall(allow_templates=["pkg:*"], allowed_suffixes=[".txt"])
    with pytest.raises(ValueError):
        tool.run(template=str(sample_template))


def test_attachment_suffix_check(sample_template, sample_attachment):
    tool = TemplateCall(allow_templates=[str(sample_template)], allowed_suffixes=[".pdf"])
    with pytest.raises(ValueError):
        tool.run(template=str(sample_template), attachments=[str(sample_attachment)])


def test_lock_template_overrides_argument(dummy_model, sample_template, tmp_path):
    copy = tmp_path / "copy.yaml"
    copy.write_text(sample_template.read_text(), encoding="utf-8")
    tool = TemplateCall(
        allow_templates=[str(copy)],
        allowed_suffixes=[".txt"],
        lock_template=str(copy),
    )
    tool.run(template="ignored", expect_json=True)
    assert dummy_model.calls


def test_expect_json_without_schema_raises(template_without_schema):
    tool = TemplateCall(allow_templates=[str(template_without_schema)])
    with pytest.raises(ValueError):
        tool.run(template=str(template_without_schema), expect_json=True)


def test_template_model_wins(monkeypatch, tmp_path, sample_attachment):
    captured = {}

    class CaptureModel:
        def prompt(self, prompt_text: str, **kwargs):
            class _Dummy:
                def text(self):
                    return "{}"

            return _Dummy()

    template = tmp_path / "with_model.yaml"
    template.write_text(
        """
model: template-model
prompt: |
  respond in json
schema_object:
  type: object
  properties:
    message:
      type: string
  required: [message]
        """.strip()
    )

    def fake_get_model(name):
        captured["model_name"] = name
        return CaptureModel()

    monkeypatch.setattr("llm.get_model", fake_get_model)
    monkeypatch.setattr("llm.get_default_model", lambda: "fallback-model")

    tool = TemplateCall(
        allow_templates=[str(template)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
    )
    tool.run(
        template=str(template),
        attachments=[str(sample_attachment)],
    )

    assert captured["model_name"] == "template-model"


def test_template_uses_global_default(monkeypatch, template_without_model, sample_attachment):
    captured = {}

    class CaptureModel:
        def prompt(self, prompt_text: str, **kwargs):
            class _Dummy:
                def text(self):
                    return "{}"

            return _Dummy()

    def fake_get_model(name):
        captured["model_name"] = name
        return CaptureModel()

    monkeypatch.setattr("llm.get_model", fake_get_model)
    monkeypatch.setattr("llm.get_default_model", lambda: "global-default")

    tool = TemplateCall(
        allow_templates=[str(template_without_model)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
    )
    tool.run(
        template=str(template_without_model),
        attachments=[str(sample_attachment)],
    )

    assert captured["model_name"] == "global-default"


def test_functions_blocks_are_ignored(monkeypatch, tmp_path):
    template = tmp_path / "with_functions.yaml"
    template.write_text(
        """
model: dummy
tools:
  - helper_tool
functions: |
  def unused():
      return "should not run"
prompt: |
  respond in json
schema_object:
  type: object
  properties:
    message:
      type: string
  required: [message]
        """.strip()
    )

    tool_instance = object()

    monkeypatch.setattr("llm.get_tools", lambda: {"helper_tool": tool_instance})
    monkeypatch.setattr("llm.get_default_model", lambda: "dummy")

    import llm.cli as cli

    def explode_tools_from_code(code):
        raise AssertionError("inline functions should be ignored")

    monkeypatch.setattr(cli, "_tools_from_code", explode_tools_from_code)

    class CaptureModel:
        def __init__(self):
            self.calls = []

        def prompt(self, prompt_text: str, **kwargs):
            self.calls.append(kwargs)

            class _Dummy:
                def text(self):
                    return "{}"

            return _Dummy()

    model_instance = CaptureModel()

    def fake_get_model(name):
        return model_instance

    monkeypatch.setattr("llm.get_model", fake_get_model)

    tool = TemplateCall(
        allow_templates=[str(template)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
    )

    tool.run(template=str(template))

    assert model_instance.calls
    assert model_instance.calls[0]["tools"] == [tool_instance]


def test_debug_mode_via_env_variable(
    monkeypatch, dummy_model, sample_template, sample_attachment, capsys
):
    """Test that LLM_DO_DEBUG environment variable enables debug output."""
    # Set environment variable
    monkeypatch.setenv("LLM_DO_DEBUG", "1")

    tool = TemplateCall(
        allow_templates=[str(sample_template)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
    )

    result = tool.run(
        template=str(sample_template),
        input="test input",
        attachments=[str(sample_attachment)],
        fragments=["procedure.md"],
        expect_json=True,
    )

    # Check that the call succeeded
    assert json.loads(result) == {"message": "ok"}

    # Capture stderr output
    captured = capsys.readouterr()

    # Check that debug output was written to stderr
    assert "[TemplateCall] Calling:" in captured.err
    assert str(sample_template) in captured.err
    assert "[TemplateCall] Model: dummy" in captured.err
    assert "[TemplateCall] Attachments:" in captured.err
    assert str(sample_attachment) in captured.err
    assert "[TemplateCall] Fragments:" in captured.err
    assert "procedure.md" in captured.err
    assert "[TemplateCall] Prompt preview:" in captured.err
    assert "[TemplateCall] Response:" in captured.err


def test_debug_mode_explicit_config(
    dummy_model, sample_template, sample_attachment, capsys
):
    """Test that debug mode can be enabled via explicit config."""
    tool = TemplateCall(
        allow_templates=[str(sample_template)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
        debug=True,
    )

    result = tool.run(
        template=str(sample_template),
        input="test input",
        attachments=[str(sample_attachment)],
        expect_json=True,
    )

    # Check that the call succeeded
    assert json.loads(result) == {"message": "ok"}

    # Capture stderr output
    captured = capsys.readouterr()

    # Check that debug output was written
    assert "[TemplateCall] Calling:" in captured.err
    assert "[TemplateCall] Model: dummy" in captured.err


def test_no_debug_output_by_default(
    dummy_model, sample_template, sample_attachment, capsys, monkeypatch
):
    """Test that debug output is not shown by default."""
    # Ensure environment variable is not set
    monkeypatch.delenv("LLM_DO_DEBUG", raising=False)

    tool = TemplateCall(
        allow_templates=[str(sample_template)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
    )

    result = tool.run(
        template=str(sample_template),
        input="test input",
        attachments=[str(sample_attachment)],
        expect_json=True,
    )

    # Check that the call succeeded
    assert json.loads(result) == {"message": "ok"}

    # Capture stderr output
    captured = capsys.readouterr()

    # Check that no debug output was written
    assert "[TemplateCall]" not in captured.err


def test_debug_explicit_false_overrides_env(
    monkeypatch, dummy_model, sample_template, sample_attachment, capsys
):
    """Test that explicit debug=False overrides environment variable."""
    # Set environment variable
    monkeypatch.setenv("LLM_DO_DEBUG", "1")

    tool = TemplateCall(
        allow_templates=[str(sample_template)],
        allowed_suffixes=[".txt"],
        max_attachments=1,
        debug=False,
    )

    result = tool.run(
        template=str(sample_template),
        input="test input",
        attachments=[str(sample_attachment)],
        expect_json=True,
    )

    # Check that the call succeeded
    assert json.loads(result) == {"message": "ok"}

    # Capture stderr output
    captured = capsys.readouterr()

    # Check that no debug output was written (explicit False wins)
    assert "[TemplateCall]" not in captured.err
