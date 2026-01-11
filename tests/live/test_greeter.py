"""Live tests for the greeter example.

This is the simplest example - just conversational, no tools.
Good for basic sanity checking that the API integration works.

Run:
    pytest tests/live/test_greeter.py -v
"""

import asyncio

from llm_do.runtime import WorkerInput

from .conftest import run_example, skip_no_llm


@skip_no_llm
def test_greeter_responds_to_message(greeter_example, default_model, approve_all_callback):
    """Test that the greeter worker responds to a simple message."""
    result = asyncio.run(
        run_example(
            greeter_example,
            WorkerInput(input="Hello, how are you?"),
            model=default_model,
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # The greeter should return some text response
    assert isinstance(result, str)
    assert len(result) > 0


@skip_no_llm
def test_greeter_tells_joke(greeter_example, default_model, approve_all_callback):
    """Test that the greeter can tell a joke when asked."""
    result = asyncio.run(
        run_example(
            greeter_example,
            WorkerInput(input="Tell me a joke"),
            model=default_model,
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    assert isinstance(result, str)
    # Should have some content (jokes are usually more than a few words)
    assert len(result) > 20
