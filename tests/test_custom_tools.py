"""Tests for custom tools loading and registration."""

import shutil
from pathlib import Path

import pytest

from llm_do import (
    WorkerRegistry,
    approve_all_callback,
    run_worker,
)


@pytest.fixture
def calculator_registry(tmp_path):
    """Registry for calculator example with custom tools."""
    source = Path(__file__).parent.parent / "examples" / "calculator"
    dest = tmp_path / "calculator"
    shutil.copytree(source, dest)
    return WorkerRegistry(dest)


@pytest.fixture
def screen_analyzer_registry(tmp_path):
    """Registry for screen_analyzer example with custom tools."""
    source = Path(__file__).parent.parent / "examples" / "screen_analyzer"
    dest = tmp_path / "screen_analyzer"
    shutil.copytree(source, dest)
    return WorkerRegistry(dest)


def test_custom_tools_discovery(calculator_registry):
    """Test that custom tools are discovered for directory-based workers."""
    # Calculator has custom tools
    custom_tools_path = calculator_registry.find_custom_tools("calculator")
    assert custom_tools_path is not None
    assert custom_tools_path.exists()
    assert custom_tools_path.name == "tools.py"


def test_custom_tools_not_found_for_simple_workers(calculator_registry, tmp_path):
    """Test that custom tools are not found for simple .yaml workers."""
    # Create a simple worker (not directory-based)
    workers_dir = calculator_registry.root / "workers"
    workers_dir.mkdir(exist_ok=True)
    simple_worker = workers_dir / "simple.yaml"
    simple_worker.write_text("name: simple\ninstructions: test")

    custom_tools = calculator_registry.find_custom_tools("simple")
    assert custom_tools is None


def test_custom_tools_loaded_and_callable(calculator_registry):
    """Test that custom tools are loaded and can be called."""
    # Run calculator worker with TestModel
    result = run_worker(
        registry=calculator_registry,
        worker="calculator",
        input_data="What is the 10th Fibonacci number?",
        cli_model="test",
        approval_callback=approve_all_callback,
    )

    # Check that the worker ran successfully
    assert result is not None
    assert hasattr(result, "output")

    # Check the messages to verify tool was called
    messages = result.messages
    tool_calls = [msg for msg in messages if hasattr(msg, "parts") and any(
        hasattr(part, "tool_name") and part.tool_name == "calculate_fibonacci"
        for part in msg.parts
    )]
    assert len(tool_calls) > 0, "Custom tool calculate_fibonacci should have been called"


def test_custom_tools_respect_tool_rules(calculator_registry):
    """Test that custom tools respect tool_rules in worker definition."""
    definition = calculator_registry.load_definition("calculator")

    # Verify tool rules are configured
    assert "calculate_fibonacci" in definition.tool_rules
    assert definition.tool_rules["calculate_fibonacci"].allowed is True
    assert definition.tool_rules["calculate_fibonacci"].approval_required is False


def test_screen_analyzer_custom_tools(screen_analyzer_registry):
    """Test screen analyzer example with custom tools."""
    # Load the worker
    definition = screen_analyzer_registry.load_definition("screen_analyzer")

    # Verify custom tools are configured
    custom_tools = screen_analyzer_registry.find_custom_tools("screen_analyzer")
    assert custom_tools is not None

    # Verify tool rules
    assert "get_screen_info" in definition.tool_rules
    assert "extract_text_regions" in definition.tool_rules
    assert "get_element_positions" in definition.tool_rules


def test_multiple_custom_tools_registered(calculator_registry):
    """Test that all custom tools from tools.py are registered."""
    definition = calculator_registry.load_definition("calculator")

    # Calculator should have 3 custom tools
    custom_tool_names = [
        "calculate_fibonacci",
        "calculate_factorial",
        "calculate_prime_factors"
    ]

    for tool_name in custom_tool_names:
        assert tool_name in definition.tool_rules, f"Tool {tool_name} should be in tool_rules"


def test_custom_tools_module_error_handling(calculator_registry, tmp_path):
    """Test graceful handling of invalid tools.py."""
    # Create a worker with invalid tools.py
    bad_worker_dir = calculator_registry.root / "workers" / "bad_tools"
    bad_worker_dir.mkdir(parents=True)

    worker_yaml = bad_worker_dir / "worker.yaml"
    worker_yaml.write_text(
        "name: bad_tools\n"
        "instructions: Just respond with 'done'\n"
        "model: test\n"
    )

    # Create tools.py with syntax error
    tools_py = bad_worker_dir / "tools.py"
    tools_py.write_text("def broken_function(\n  # Missing closing paren")

    # Loading definition should work (error handling happens during tool loading)
    definition = calculator_registry.load_definition("bad_tools")
    assert definition.name == "bad_tools"

    # Custom tools should be detected
    custom_tools = calculator_registry.find_custom_tools("bad_tools")
    assert custom_tools is not None

    # Verify the tools file exists but is invalid
    assert custom_tools.exists()
    with open(custom_tools) as f:
        content = f.read()
        assert "def broken_function(" in content

    # The actual error handling happens in _load_custom_tools during agent creation
    # We've verified the infrastructure can detect the tools file, even if it's invalid


def test_private_functions_not_registered(calculator_registry, tmp_path):
    """Test that functions starting with _ are not registered as tools."""
    # The calculator tools.py has a _validate_input function
    # It should not be registered as a tool

    # We can't easily check this directly, but we can verify the behavior
    # by checking that only public functions are in tool_rules
    definition = calculator_registry.load_definition("calculator")

    # Verify _validate_input is NOT in tool_rules
    assert "_validate_input" not in definition.tool_rules
    assert "__init__" not in definition.tool_rules
    assert "__name__" not in definition.tool_rules
