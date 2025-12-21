"""Tests for custom tools loading and registration."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic_ai.models.test import TestModel

from llm_do import (
    ApprovalController,
    WorkerContext,
    WorkerDefinition,
    WorkerRegistry,
    run_worker_async,
)
from llm_do.custom_toolset import CustomToolset


# Sample tools.py content for testing
SAMPLE_TOOLS_PY = '''
"""Custom calculation tools for testing."""


def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def calculate_factorial(n: int) -> int:
    """Calculate the factorial of n (n!)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def calculate_prime_factors(n: int) -> list[int]:
    """Find all prime factors of a number."""
    if n <= 1:
        raise ValueError("n must be greater than 1")
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


def _private_helper(x: int) -> int:
    """Private helper function - should not be registered as a tool."""
    return x * 2
'''

SAMPLE_WORKER = '''---
name: calculator
description: Mathematical calculator with custom computation tools
toolsets:
  custom:
    calculate_factorial: {}
    calculate_fibonacci: {}
    calculate_prime_factors: {}
---

You are a mathematical calculator assistant with access to custom tools.
When the user asks for calculations, use the appropriate tool.
'''


@pytest.fixture
def custom_tools_registry(tmp_path):
    """Registry with a worker that has custom tools."""
    # Create main.worker
    main_worker = tmp_path / "main.worker"
    main_worker.write_text(SAMPLE_WORKER)

    # Create tools.py
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(SAMPLE_TOOLS_PY)

    return WorkerRegistry(tmp_path)


def test_custom_tools_discovery(custom_tools_registry):
    """Test that custom tools are discovered for workers with tools.py."""
    custom_tools_path = custom_tools_registry.find_custom_tools("main")
    assert custom_tools_path is not None
    assert custom_tools_path.exists()
    assert custom_tools_path.name == "tools.py"


def test_custom_tools_not_found_for_simple_workers(tmp_path):
    """Test that custom tools are not found for workers without tools.py."""
    # Create a simple worker without tools.py
    simple_worker = tmp_path / "simple.worker"
    simple_worker.write_text("---\nname: simple\n---\ntest")

    registry = WorkerRegistry(tmp_path)
    custom_tools = registry.find_custom_tools("simple")
    assert custom_tools is None


def test_custom_tools_loaded_and_callable(custom_tools_registry):
    """Test that custom tools are loaded and can be called."""
    model = TestModel(call_tools=["calculate_fibonacci"])

    result = asyncio.run(
        run_worker_async(
            registry=custom_tools_registry,
            worker="main",
            input_data="What is the 10th Fibonacci number?",
            cli_model=model,
            approval_controller=ApprovalController(mode="approve_all"),
        )
    )

    assert result is not None
    assert hasattr(result, "output")

    # Check the messages to verify tool was called
    messages = result.messages
    tool_calls = [msg for msg in messages if hasattr(msg, "parts") and any(
        hasattr(part, "tool_name") and part.tool_name == "calculate_fibonacci"
        for part in msg.parts
    )]
    assert len(tool_calls) > 0, "Custom tool calculate_fibonacci should have been called"


def test_custom_tools_allowlist(custom_tools_registry):
    """Test that custom tools are listed in custom_tools allowlist."""
    definition = custom_tools_registry.load_definition("main")

    custom_tools = (definition.toolsets or {}).get("custom", {})
    assert "calculate_fibonacci" in custom_tools
    assert "calculate_factorial" in custom_tools
    assert "calculate_prime_factors" in custom_tools


def test_multiple_custom_tools_registered(custom_tools_registry):
    """Test that all custom tools from tools.py are registered."""
    definition = custom_tools_registry.load_definition("main")

    custom_tool_names = [
        "calculate_fibonacci",
        "calculate_factorial",
        "calculate_prime_factors"
    ]

    custom_tools = (definition.toolsets or {}).get("custom", {})
    for tool_name in custom_tool_names:
        assert tool_name in custom_tools, f"Tool {tool_name} should be in custom_tools"


def test_custom_tools_module_error_handling(tmp_path):
    """Test graceful handling of invalid tools.py."""
    # Create a worker directory with invalid tools.py
    bad_worker_dir = tmp_path / "bad_tools"
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

    registry = WorkerRegistry(tmp_path)

    # Loading definition should work (error handling happens during tool loading)
    definition = registry.load_definition("bad_tools")
    assert definition.name == "bad_tools"

    # Custom tools should be detected
    custom_tools = registry.find_custom_tools("bad_tools")
    assert custom_tools is not None

    # Verify the tools file exists but is invalid
    assert custom_tools.exists()
    with open(custom_tools) as f:
        content = f.read()
        assert "def broken_function(" in content


def test_private_functions_not_registered(custom_tools_registry):
    """Test that functions starting with _ are not registered as tools.

    Only functions listed in custom_tools are registered.
    Private functions (_private_helper) are not listed, so they won't be registered.
    """
    definition = custom_tools_registry.load_definition("main")

    custom_tools = (definition.toolsets or {}).get("custom", {})
    assert "_private_helper" not in custom_tools
    assert "__init__" not in custom_tools
    assert "__name__" not in custom_tools


def test_custom_tools_require_allowlist(tmp_path):
    """Test that custom tools must be explicitly listed in custom_tools to be registered."""
    # Create a worker with tools.py but no custom_tools in config
    test_worker_dir = tmp_path / "test_no_allowlist"
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

    registry = WorkerRegistry(tmp_path)

    # Load the worker - should succeed
    definition = registry.load_definition("test_no_allowlist")
    assert definition.name == "test_no_allowlist"

    # Verify custom tools path is found
    custom_tools = registry.find_custom_tools("test_no_allowlist")
    assert custom_tools is not None

    # Verify custom_tools is empty (not configured in worker)
    custom_tools = (definition.toolsets or {}).get("custom", {})
    assert len(custom_tools) == 0


def test_custom_tools_approval_via_decorator(tmp_path):
    """Test that custom tools can require approval via @requires_approval decorator."""
    test_worker_dir = tmp_path / "test_approval_decorator"
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

    registry = WorkerRegistry(tmp_path)
    definition = registry.load_definition("test_approval_decorator")

    # Verify the tool is in the allowlist
    custom_tools = (definition.toolsets or {}).get("custom", {})
    assert "calculate_with_approval" in custom_tools


def test_custom_tools_rejects_non_whitelisted_tool(tmp_path):
    """Test that calling a non-whitelisted tool raises ValueError.

    This simulates an LLM hallucinating a tool that exists in tools.py
    but is not in the whitelist config.
    """
    # Create a worker with tools.py containing multiple functions
    # but only whitelist one of them
    test_worker_dir = tmp_path / "workers" / "test_whitelist"
    test_worker_dir.mkdir(parents=True)

    tools_py = test_worker_dir / "tools.py"
    tools_py.write_text(
        "def allowed_tool(x: int) -> int:\n"
        "    '''An allowed tool.'''\n"
        "    return x * 2\n"
        "\n"
        "def secret_tool(x: int) -> int:\n"
        "    '''A tool that exists but is NOT whitelisted.'''\n"
        "    return x * 100\n"
    )

    # Only whitelist allowed_tool, not secret_tool
    config = {"allowed_tool": {"pre_approved": False}}

    toolset = CustomToolset(config=config)

    # Create mock ctx with deps that has worker info and tools_path
    mock_worker = MagicMock()
    mock_worker.name = "test_whitelist"
    mock_deps = MagicMock()
    mock_deps.worker = mock_worker
    mock_deps.custom_tools_path = tools_py
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_deps

    # Load the module and verify only allowed_tool is exposed
    tools = asyncio.run(toolset.get_tools(mock_ctx))
    assert "allowed_tool" in tools
    assert "secret_tool" not in tools

    # Now simulate LLM hallucinating secret_tool call
    # This should raise ValueError
    with pytest.raises(ValueError, match="Unknown custom tool: secret_tool"):
        asyncio.run(toolset.call_tool("secret_tool", {"x": 5}, mock_ctx, None))


def _build_custom_tool_ctx(tools_py: Path, *, depth: int = 0) -> MagicMock:
    worker = WorkerDefinition(name="custom_tools_ctx")
    deps = WorkerContext(
        worker=worker,
        effective_model=None,
        approval_controller=ApprovalController(mode="approve_all"),
        depth=depth,
        custom_tools_path=tools_py,
    )
    mock_ctx = MagicMock()
    mock_ctx.deps = deps
    return mock_ctx


def test_custom_tools_context_injection(tmp_path):
    """Test that @tool_context injects WorkerContext into custom tools."""
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(
        "from llm_do import tool_context\n\n"
        "@tool_context\n"
        "def add_depth(value: int, ctx) -> int:\n"
        "    return value + ctx.depth\n"
    )

    toolset = CustomToolset(config={"add_depth": {}})
    mock_ctx = _build_custom_tool_ctx(tools_py, depth=3)

    tools = asyncio.run(toolset.get_tools(mock_ctx))
    result = asyncio.run(
        toolset.call_tool("add_depth", {"value": 4}, mock_ctx, tools["add_depth"])
    )

    assert result == 7


def test_custom_tools_context_schema_omits_ctx(tmp_path):
    """Test that injected context params are excluded from tool schemas."""
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(
        "from llm_do import tool_context\n\n"
        "@tool_context\n"
        "def add_depth(value: int, ctx) -> int:\n"
        "    return value + ctx.depth\n"
    )

    toolset = CustomToolset(config={"add_depth": {}})
    mock_ctx = _build_custom_tool_ctx(tools_py)
    tools = asyncio.run(toolset.get_tools(mock_ctx))
    schema = tools["add_depth"].tool_def.parameters_json_schema

    assert "ctx" not in schema.get("properties", {})
    assert "ctx" not in schema.get("required", [])
    assert "value" in schema.get("properties", {})


def test_custom_tools_context_requires_param(tmp_path):
    """Test that @tool_context requires the declared parameter to exist."""
    tools_py = tmp_path / "tools.py"
    tools_py.write_text(
        "from llm_do import tool_context\n\n"
        "@tool_context\n"
        "def bad_tool(value: int) -> int:\n"
        "    return value\n"
    )

    toolset = CustomToolset(config={"bad_tool": {}})
    mock_ctx = _build_custom_tool_ctx(tools_py)

    with pytest.raises(ValueError, match="marked with @tool_context"):
        asyncio.run(toolset.get_tools(mock_ctx))
