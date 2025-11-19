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
