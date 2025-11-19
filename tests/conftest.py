from __future__ import annotations

import json
from pathlib import Path
import pytest


class DummyResponse:
    def __init__(self, text: str):
        self._text = text

    def text(self) -> str:
        return self._text


class DummyModel:
    def __init__(self, response_text: str = '{"message": "ok"}'):
        self.calls = []
        self.response_text = response_text

    def prompt(self, prompt_text: str, **kwargs):
        self.calls.append((prompt_text, kwargs))
        return DummyResponse(self.response_text)


@pytest.fixture
def dummy_model(monkeypatch):
    model = DummyModel()

    def fake_get_model(name):
        return model

    monkeypatch.setattr("llm.get_model", fake_get_model)
    monkeypatch.setattr("llm.get_default_model", lambda: "dummy")
    return model


@pytest.fixture
def sample_attachment(tmp_path: Path) -> Path:
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")
    return path


@pytest.fixture
def sample_template(tmp_path: Path) -> Path:
    template = tmp_path / "template.yaml"
    template.write_text(
        """
model: dummy
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
    return template
