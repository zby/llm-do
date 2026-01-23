import json

import pytest

from llm_do.runtime.events import ToolCallEvent, ToolResultEvent

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

        def _parse_args(event):
            if isinstance(event.args, dict):
                return event.args
            if isinstance(event.args, str):
                try:
                    return json.loads(event.args)
                except json.JSONDecodeError:
                    return {}
            if event.args_json:
                try:
                    return json.loads(event.args_json)
                except json.JSONDecodeError:
                    return {}
            return {}

        def on_event(event):
            nonlocal split_index, merge_index
            if isinstance(event, ToolCallEvent) and event.tool_name == "summarizer":
                split_index += 1
                args = _parse_args(event)
                path = args.get("path", "")
                start = args.get("start")
                end = args.get("end")
                span = None
                if isinstance(start, int) and isinstance(end, int):
                    span = end - start
                print(f"[split {split_index}] path={path} start={start} end={end} span={span}")
            elif isinstance(event, ToolResultEvent) and event.tool_name == "summarizer":
                merge_index += 1
                output_text = str(event.content)
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
