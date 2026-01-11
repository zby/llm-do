"""Live tests for the code_analyzer example.

Tests shell tool integration with pattern-based approval rules.

Run:
    pytest tests/live/test_code_analyzer.py -v
"""

import asyncio
from pathlib import Path

from llm_do.runtime import WorkerInput

from .conftest import run_example, skip_no_llm


@skip_no_llm
def test_code_analyzer_count_files(code_analyzer_example, default_model, approve_all_callback):
    """Test that code_analyzer can count files using shell commands."""
    # The test runs in a temp copy of the code_analyzer example
    # Create some test files to analyze
    Path("test_file1.py").write_text("# test file 1\nprint('hello')")
    Path("test_file2.py").write_text("# test file 2\nprint('world')")

    result = asyncio.run(
        run_example(
            code_analyzer_example,
            WorkerInput(input="How many Python files are there?"),
            model=default_model,
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # Should mention there are 2 Python files
    assert "2" in result


@skip_no_llm
def test_code_analyzer_find_pattern(code_analyzer_example, default_model, approve_all_callback):
    """Test that code_analyzer can search for patterns in code."""
    # Create test files with specific patterns
    Path("sample.py").write_text("# TODO: implement this\ndef my_function():\n    pass")

    result = asyncio.run(
        run_example(
            code_analyzer_example,
            WorkerInput(input="Find all TODO comments"),
            model=default_model,
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # Should find and mention the TODO
    assert "TODO" in result or "todo" in result.lower()


@skip_no_llm
def test_code_analyzer_line_count(code_analyzer_example, default_model, approve_all_callback):
    """Test that code_analyzer can count lines of code."""
    # Create test files with known line counts
    Path("lines_test.py").write_text("line1\nline2\nline3\nline4\nline5\n")

    result = asyncio.run(
        run_example(
            code_analyzer_example,
            WorkerInput(input="Count the lines in lines_test.py"),
            model=default_model,
            approval_callback=approve_all_callback,
        )
    )

    assert result is not None
    # Should mention 5 lines (or close to it depending on how it counts)
    assert any(num in result for num in ["5", "five"])
