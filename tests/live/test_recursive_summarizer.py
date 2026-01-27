import json

import pytest
from pydantic_ai.messages import FunctionToolCallEvent, FunctionToolResultEvent

from .conftest import skip_no_llm


def _preview_words(text: str, limit: int = 16) -> str:
    words = text.split()
    preview = " ".join(words[:limit])
    if len(words) > limit:
        preview += " ..."
    return preview


@skip_no_llm
@pytest.mark.anyio
async def test_recursive_summarizer_runs(recursive_summarizer_example, default_model, request):
    from .conftest import run_example

    verbose = request.config.getoption("verbose")
    on_event = None
    if verbose >= 2:
        split_index = 0
        merge_index = 0

        def _parse_args(tool_part):
            if isinstance(tool_part.args, dict):
                return tool_part.args
            if isinstance(tool_part.args, str):
                try:
                    return json.loads(tool_part.args)
                except json.JSONDecodeError:
                    return {}
            if hasattr(tool_part, "args_as_json_str"):
                try:
                    return json.loads(tool_part.args_as_json_str())
                except json.JSONDecodeError:
                    return {}
            return {}

        def on_event(event):
            nonlocal split_index, merge_index
            if isinstance(event.event, FunctionToolCallEvent) and event.event.part.tool_name == "summarizer":
                split_index += 1
                args = _parse_args(event.event.part)
                path = args.get("path", "")
                start = args.get("start")
                end = args.get("end")
                span = None
                if isinstance(start, int) and isinstance(end, int):
                    span = end - start
                print(f"[split {split_index}] path={path} start={start} end={end} span={span}")
            elif isinstance(event.event, FunctionToolResultEvent) and event.event.result.tool_name == "summarizer":
                merge_index += 1
                output_text = str(event.event.result.content)
                char_count = len(output_text)
                word_count = len(output_text.split())
                preview = _preview_words(output_text)
                print(f"[merge {merge_index}] chars={char_count} words={word_count} preview={preview}")

    result = await run_example(
        recursive_summarizer_example,
        "sample_input.txt",
        model=default_model,
        max_depth=10,
        on_event=on_event,
        verbosity=1 if verbose >= 2 else 0,
    )

    assert isinstance(result, str)
    assert result.strip()
