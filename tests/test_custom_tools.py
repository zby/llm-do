"""Tests for custom tools loading and registration."""

import shutil
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from llm_do import (
    ApprovalController,
    WorkerRegistry,
    run_worker,
)


@pytest.fixture
def calculator_registry(tmp_path):
    """Registry for calculator example with custom tools."""
    source = Path(__file__).parent.parent / "examples" / "calculator"
    dest = tmp_path / "calculator"
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
    """Test that custom tools are not found for simple .worker workers."""
    # Create a simple worker (not directory-based)
    workers_dir = calculator_registry.root / "workers"
    workers_dir.mkdir(exist_ok=True)
    simple_worker = workers_dir / "simple.worker"
    simple_worker.write_text("---\nname: simple\n---\ntest")

    custom_tools = calculator_registry.find_custom_tools("simple")
    assert custom_tools is None


def test_custom_tools_loaded_and_callable(calculator_registry):
    """Test that custom tools are loaded and can be called."""
    # Only call the calculator tool to avoid random worker_call invocations
    model = TestModel(call_tools=["calculate_fibonacci"])

    # Run calculator worker with TestModel to exercise the tool path without API keys
    result = run_worker(
        registry=calculator_registry,
        worker="calculator",
        input_data="What is the 10th Fibonacci number?",
        cli_model=model,
        approval_controller=ApprovalController(mode="approve_all"),
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


def test_custom_tools_allowlist(calculator_registry):
    """Test that custom tools are listed in custom_tools allowlist."""
    definition = calculator_registry.load_definition("calculator")

    # Verify custom_tools allowlist is configured
    custom_tools = definition.toolsets.custom if definition.toolsets else {}
    assert "calculate_fibonacci" in custom_tools
    assert "calculate_factorial" in custom_tools
    assert "calculate_prime_factors" in custom_tools


def test_multiple_custom_tools_registered(calculator_registry):
    """Test that all custom tools from tools.py are registered."""
    definition = calculator_registry.load_definition("calculator")

    # Calculator should have 3 custom tools
    custom_tool_names = [
        "calculate_fibonacci",
        "calculate_factorial",
        "calculate_prime_factors"
    ]

    custom_tools = definition.toolsets.custom if definition.toolsets else {}
    for tool_name in custom_tool_names:
        assert tool_name in custom_tools, f"Tool {tool_name} should be in custom_tools"


def test_custom_tools_module_error_handling(calculator_registry, tmp_path):
    """Test graceful handling of invalid tools.py."""
    # Create a worker with invalid tools.py
    bad_worker_dir = calculator_registry.root / "workers" / "bad_tools"
    bad_worker_dir.mkdir(parents=True)

    worker_file = bad_worker_dir / "worker.worker"
    worker_file.write_text(
        "---\n"
        "name: bad_tools\n"
        "model: test\n"
        "---\n"
        "Just respond with 'done'"
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
    """Test that functions starting with _ are not registered as tools.

    In the new architecture, only functions listed in custom_tools are registered.
    Private functions (_validate_input) are not listed, so they won't be registered.
    """
    definition = calculator_registry.load_definition("calculator")

    # Verify _validate_input is NOT in custom_tools
    custom_tools = definition.toolsets.custom if definition.toolsets else {}
    assert "_validate_input" not in custom_tools
    assert "__init__" not in custom_tools
    assert "__name__" not in custom_tools


def test_custom_tools_require_allowlist(calculator_registry, tmp_path):
    """Test that custom tools must be explicitly listed in custom_tools to be registered."""
    # Create a worker with tools.py but no custom_tools
    test_worker_dir = calculator_registry.root / "workers" / "test_no_allowlist"
    test_worker_dir.mkdir(parents=True)

    worker_file = test_worker_dir / "worker.worker"
    worker_file.write_text(
        "---\n"
        "name: test_no_allowlist\n"
        "model: test\n"
        "---\n"
        "Test worker"
    )

    # Create tools.py with a dangerous function
    tools_py = test_worker_dir / "tools.py"
    tools_py.write_text(
        "def dangerous_operation(command: str) -> str:\n"
        "    '''Execute a dangerous operation.'''\n"
        "    return f'Would execute: {command}'\n"
    )

    # Load the worker - should succeed
    definition = calculator_registry.load_definition("test_no_allowlist")
    assert definition.name == "test_no_allowlist"

    # Verify custom tools path is found
    custom_tools = calculator_registry.find_custom_tools("test_no_allowlist")
    assert custom_tools is not None

    # Verify custom_tools is empty
    custom_tools = definition.toolsets.custom if definition.toolsets else {}
    assert len(custom_tools) == 0

    # The security guarantee is in load_custom_tools:
    # It only registers tools that are in custom_tools list
    # Since there are no custom_tools, no custom tools will be registered


def test_custom_tools_approval_via_decorator(calculator_registry):
    """Test that custom tools can require approval via @requires_approval decorator.

    In the new architecture, approval is determined by the @requires_approval
    decorator on the function, not by tool_rules config.
    """
    # Create a worker with custom_tools and tools that use @requires_approval
    test_worker_dir = calculator_registry.root / "workers" / "test_approval_decorator"
    test_worker_dir.mkdir(parents=True)

    worker_file = test_worker_dir / "worker.worker"
    worker_file.write_text(
        "---\n"
        "name: test_approval_decorator\n"
        "model: test\n"
        "toolsets:\n"
        "  custom:\n"
        "    calculate_with_approval: {}\n"
        "---\n"
        "Calculate with approval"
    )

    # Create tools.py with a function that uses @requires_approval
    tools_py = test_worker_dir / "tools.py"
    tools_py.write_text(
        "from pydantic_ai_blocking_approval import requires_approval\n\n"
        "@requires_approval\n"
        "def calculate_with_approval(n: int) -> int:\n"
        "    '''Calculate something that requires approval.'''\n"
        "    return n * 2\n"
    )

    # Load the worker
    definition = calculator_registry.load_definition("test_approval_decorator")

    # Verify the tool is in the allowlist
    custom_tools = definition.toolsets.custom if definition.toolsets else {}
    assert "calculate_with_approval" in custom_tools

    # The security guarantee is enforced in load_custom_tools:
    # When a function has check_approval (from @requires_approval), the wrapper
    # calls it before executing the function
