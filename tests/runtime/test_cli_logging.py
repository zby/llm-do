import io
import json

from pydantic_ai.messages import ModelRequest, UserPromptPart

from llm_do.cli.main import _make_message_log_callback


def test_message_log_callback_emits_jsonl_records() -> None:
    stream = io.StringIO()
    callback = _make_message_log_callback(stream)
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelRequest(parts=[UserPromptPart(content="world")]),
    ]

    callback("agent", 2, messages)

    lines = stream.getvalue().splitlines()
    assert len(lines) == len(messages)
    for idx, line in enumerate(lines):
        record = json.loads(line)
        assert record["seq"] == idx
        assert record["agent"] == "agent"
        assert record["depth"] == 2
        assert "message" in record
