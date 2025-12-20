"""Live tests for the greeter example.

This is the simplest example - just conversational, no tools.
Good for basic sanity checking that the API integration works.

Run:
    pytest tests/live/test_greeter.py -v
"""

import asyncio

from llm_do import run_worker_async

from .conftest import skip_no_llm


@skip_no_llm
def test_greeter_responds_to_message(greeter_registry, default_model, approve_all_controller):
    """Test that the greeter worker responds to a simple message."""
    result = asyncio.run(
        run_worker_async(
            registry=greeter_registry,
            worker="main",
            input_data="Hello, how are you?",
            cli_model=default_model,
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    # The greeter should return some text response
    assert isinstance(result.output, str)
    assert len(result.output) > 0


@skip_no_llm
def test_greeter_tells_joke(greeter_registry, default_model, approve_all_controller):
    """Test that the greeter can tell a joke when asked."""
    result = asyncio.run(
        run_worker_async(
            registry=greeter_registry,
            worker="main",
            input_data="Tell me a joke",
            cli_model=default_model,
            approval_controller=approve_all_controller,
        )
    )

    assert result is not None
    assert result.output is not None
    assert isinstance(result.output, str)
    # Should have some content (jokes are usually more than a few words)
    assert len(result.output) > 20
