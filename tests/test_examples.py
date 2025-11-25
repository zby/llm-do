"""Integration tests for all example workers using TestModel.

These tests verify that all the example workers in examples/ directory
can be loaded and executed successfully using PydanticAI's TestModel.
This ensures the examples stay working as the codebase evolves.

## Testing Philosophy: CWD Matters

Workers with sandboxes that use relative paths (like `./notes` or `./input`)
depend on CWD for correct path resolution, because the Sandbox resolves
relative paths from CWD (not from the registry root).

To match real-world usage:
1. Copy example to tmp_path (for test isolation)
2. Change CWD to the example directory (via monkeypatch.chdir)
3. Now relative sandbox paths resolve correctly

This mimics how users actually run the examples:
    cd examples/approvals_demo
    llm-do save_note "My note"

Without changing CWD, relative paths would resolve from the project root,
causing files to be written to the wrong location.
"""
import shutil
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from llm_do import (
    WorkerRegistry,
    approve_all_callback,
    run_worker,
    strict_mode_callback,
)
from tests.tool_calling_model import ToolCallingModel


def _copy_example_directory(example_name: str, tmp_path: Path) -> Path:
    """Copy an example directory to tmp_path and return the path.

    Args:
        example_name: Name of the example (e.g., "greeter", "pitchdeck_eval")
        tmp_path: Pytest tmp_path fixture

    Returns:
        Path to the copied example directory
    """
    source = Path(__file__).parent.parent / "examples" / example_name
    dest = tmp_path / example_name
    shutil.copytree(source, dest)
    return dest


@pytest.fixture
def greeter_registry(tmp_path):
    """Registry for the greeter example worker."""

    example_path = _copy_example_directory("greeter", tmp_path)
    return WorkerRegistry(example_path)


@pytest.fixture
def approvals_demo_registry(tmp_path, monkeypatch):
    """Registry for the approvals demo example."""
    example_path = _copy_example_directory("approvals_demo", tmp_path)
    # Change CWD to example directory so relative sandbox paths resolve correctly
    monkeypatch.chdir(example_path)
    return WorkerRegistry(example_path)


@pytest.fixture
def pitchdeck_eval_registry(tmp_path, monkeypatch):
    """Registry for the pitchdeck_eval example."""
    example_path = _copy_example_directory("pitchdeck_eval", tmp_path)
    # Change CWD to example directory so relative sandbox paths resolve correctly
    monkeypatch.chdir(example_path)
    return WorkerRegistry(example_path)


def test_greeter_example(greeter_registry):
    """Test the greeter example - simple conversational worker.

    This tests that:
    - Worker definition loads correctly
    - Worker can respond to user input
    - No tools are required (pure conversational)
    """
    # Use TestModel with no tool calling (greeter doesn't use tools)
    model = TestModel(call_tools=[], custom_output_text="Hello! Here's a joke for you...")

    result = run_worker(
        registry=greeter_registry,
        worker="greeter",
        input_data="Tell me a joke",
        cli_model=model,
    )

    # TestModel should execute successfully
    assert result is not None
    assert result.output is not None


def test_greeter_with_different_inputs(greeter_registry):
    """Test greeter handles various input types."""
    model = TestModel(call_tools=[], custom_output_text="Response text")

    inputs = [
        "Hello there!",
        "What's the weather like?",
        {"message": "structured input"},
    ]

    for input_data in inputs:
        result = run_worker(
            registry=greeter_registry,
            worker="greeter",
            input_data=input_data,
            cli_model=model,
        )
        assert result is not None


def test_save_note_example(approvals_demo_registry, tool_calling_model_cls):
    """Test the save_note example - sandbox write with approval.

    This tests that:
    - Worker loads with sandbox configuration
    - Tool is actually called to write the file
    - Approval system works with approve_all
    - File is written to the sandboxed directory

    Note: The fixture changes CWD to the example directory, so relative
    sandbox paths (like ./notes) resolve correctly.
    """
    from pathlib import Path

    # Since CWD is the example directory, ./notes resolves correctly
    notes_dir = Path("notes")
    log_file = notes_dir / "activity.log"

    # Clean up any existing activity.log from the copied example
    if log_file.exists():
        log_file.unlink()

    # Mock model that actually calls write_file
    note_content = "2025-11-22 14:30 • Test note from integration test"
    model = tool_calling_model_cls([
        {
            "name": "write_file",
            "args": {
                "path": "notes/activity.log",
                "content": note_content,
            },
        }
    ])

    result = run_worker(
        registry=approvals_demo_registry,
        worker="save_note",
        input_data={"note": "Test note from integration test"},
        cli_model=model,
        approval_callback=approve_all_callback,
    )

    # Verify the worker executed successfully
    assert result is not None
    assert result.output == "Task completed"

    # Verify the file was actually written
    assert log_file.exists(), "activity.log should be created"
    assert log_file.read_text() == note_content


def test_save_note_with_string_input(approvals_demo_registry, tool_calling_model_cls):
    """Test save_note with plain string input."""
    from pathlib import Path

    # Since CWD is the example directory, ./notes resolves correctly
    notes_dir = Path("notes")
    log_file = notes_dir / "activity.log"

    # Clean up any existing activity.log from the copied example
    if log_file.exists():
        log_file.unlink()

    note_content = "2025-11-22 15:00 • Plain string note"
    model = tool_calling_model_cls([
        {
            "name": "write_file",
            "args": {
                "path": "notes/activity.log",
                "content": note_content,
            },
        }
    ])

    result = run_worker(
        registry=approvals_demo_registry,
        worker="save_note",
        input_data="Plain string note",
        cli_model=model,
        approval_callback=approve_all_callback,
    )

    assert result is not None
    assert result.output == "Task completed"

    # Verify the file was written
    assert log_file.exists()
    assert log_file.read_text() == note_content


def test_save_note_strict_mode_blocks_write(approvals_demo_registry, tool_calling_model_cls):
    """Test that save_note is blocked in strict mode (no approval)."""
    from pathlib import Path

    # Since CWD is the example directory, ./notes resolves correctly
    notes_dir = Path("notes")
    log_file = notes_dir / "activity.log"

    # Clean up any existing activity.log from the copied example
    if log_file.exists():
        log_file.unlink()

    # Mock model that tries to write
    model = tool_calling_model_cls([
        {
            "name": "write_file",
            "args": {
                "path": "notes/activity.log",
                "content": "Should be blocked",
            },
        }
    ])

    # Strict mode should reject the write
    with pytest.raises(PermissionError, match="Strict mode"):
        run_worker(
            registry=approvals_demo_registry,
            worker="save_note",
            input_data="This should be blocked",
            cli_model=model,
            approval_callback=strict_mode_callback,
        )

    # Verify no file was written (it was deleted before the test)
    assert not log_file.exists(), "File should not be created when blocked"


def test_pitch_evaluator_example(pitchdeck_eval_registry, tmp_path):
    """Test the pitch_evaluator example - PDF attachment handling.

    This tests that:
    - Worker loads with attachment policy
    - Worker can handle PDF attachments
    - Attachment validation works
    """
    # Use TestModel with no tool calling and markdown output
    model = TestModel(
        call_tools=[],
        custom_output_text="# Test Company\n\n**Verdict:** GO\n\n## Summary\n\nAnalysis complete."
    )

    # Create a dummy PDF file to attach
    pdf_file = tmp_path / "test_deck.pdf"
    pdf_file.write_text("Mock PDF content", encoding="utf-8")

    result = run_worker(
        registry=pitchdeck_eval_registry,
        worker="pitch_evaluator",
        input_data="Evaluate this deck",
        cli_model=model,
        attachments=[pdf_file],
    )

    assert result is not None
    assert result.output is not None


def test_pitch_evaluator_attachment_validation(pitchdeck_eval_registry, tmp_path):
    """Test that pitch_evaluator rejects non-PDF attachments."""
    # Create a non-PDF file
    txt_file = tmp_path / "not_a_pdf.txt"
    txt_file.write_text("This is not a PDF", encoding="utf-8")

    # Should fail attachment validation (only .pdf allowed)
    with pytest.raises(ValueError, match="not allowed"):
        run_worker(
            registry=pitchdeck_eval_registry,
            worker="pitch_evaluator",
            input_data="Evaluate this",
            cli_model=None,  # Won't get to model execution
            attachments=[txt_file],
        )


def test_pitch_evaluator_attachment_count_limit(pitchdeck_eval_registry, tmp_path):
    """Test that pitch_evaluator enforces max_attachments=1."""
    # Create multiple PDF files
    pdf1 = tmp_path / "deck1.pdf"
    pdf2 = tmp_path / "deck2.pdf"
    pdf1.write_text("PDF 1", encoding="utf-8")
    pdf2.write_text("PDF 2", encoding="utf-8")

    # Should fail because max_attachments=1
    with pytest.raises(ValueError, match="Too many attachments"):
        run_worker(
            registry=pitchdeck_eval_registry,
            worker="pitch_evaluator",
            input_data="Evaluate these",
            cli_model=None,  # Won't get to model execution
            attachments=[pdf1, pdf2],
        )


def test_pitch_orchestrator_example(pitchdeck_eval_registry):
    """Test the pitch_orchestrator example - multi-worker delegation.

    This tests that:
    - Worker loads with sandbox configuration
    - Worker loads with allow_workers delegation list
    - Worker can execute with sandboxes configured
    - Delegation setup is correct (doesn't test actual delegation with TestModel)

    Note: The fixture changes CWD to the example directory, so relative
    sandbox paths (like ./input and ./evaluations) resolve correctly.
    """
    from pathlib import Path

    # Use TestModel with no tool calling
    model = TestModel(
        call_tools=[],
        custom_output_text="Processed all pitch decks successfully"
    )

    # Since CWD is the example directory, these paths resolve correctly
    input_dir = Path("input")
    eval_dir = Path("evaluations")

    # The sandbox directories should already exist (copied from example)
    # but create them if needed
    input_dir.mkdir(exist_ok=True)
    eval_dir.mkdir(exist_ok=True)

    # Create a test PDF in the input directory
    test_pdf = input_dir / "test_deck.pdf"
    test_pdf.write_text("Mock pitch deck PDF", encoding="utf-8")

    result = run_worker(
        registry=pitchdeck_eval_registry,
        worker="pitch_orchestrator",
        input_data="Evaluate all pitch decks",
        cli_model=model,
        approval_callback=approve_all_callback,
    )

    assert result is not None
    assert result.output is not None


def test_pitch_orchestrator_sandboxes_configured(pitchdeck_eval_registry):
    """Test that pitch_orchestrator has correct sandbox configuration."""
    definition = pitchdeck_eval_registry.load_definition("pitch_orchestrator")

    # Verify sandboxes are configured
    assert definition.sandbox is not None
    assert "input" in definition.sandbox.paths
    assert "evaluations" in definition.sandbox.paths

    # Verify input is read-only
    assert definition.sandbox.paths["input"].mode == "ro"

    # Verify evaluations is writable
    assert definition.sandbox.paths["evaluations"].mode == "rw"

    # Verify allowed suffixes
    assert ".pdf" in definition.sandbox.paths["input"].suffixes

def test_all_example_workers_load_successfully():
    """Test that all example worker definitions can be loaded.

    This is a smoke test to catch any YAML syntax errors or
    missing required fields in the example worker definitions.
    """
    examples_dir = Path(__file__).parent.parent / "examples"

    # Greeter (in examples/greeter/workers/greeter.yaml)
    greeter_registry = WorkerRegistry(examples_dir / "greeter")
    greeter_def = greeter_registry.load_definition("greeter")
    assert greeter_def.name == "greeter"
    assert greeter_def.description is not None

    # Save note (in examples/approvals_demo/workers/save_note.yaml)
    approvals_registry = WorkerRegistry(examples_dir / "approvals_demo")
    save_note_def = approvals_registry.load_definition("save_note")
    assert save_note_def.name == "save_note"
    assert save_note_def.sandbox is not None
    assert "notes" in save_note_def.sandbox.paths

    # Pitch evaluator (in examples/pitchdeck_eval/workers/pitch_evaluator.yaml)
    pitch_registry = WorkerRegistry(examples_dir / "pitchdeck_eval")
    evaluator_def = pitch_registry.load_definition("pitch_evaluator")
    assert evaluator_def.name == "pitch_evaluator"
    assert evaluator_def.attachment_policy is not None

    # Pitch orchestrator (in examples/pitchdeck_eval/workers/pitch_orchestrator.yaml)
    orchestrator_def = pitch_registry.load_definition("pitch_orchestrator")
    assert orchestrator_def.name == "pitch_orchestrator"
    assert orchestrator_def.allow_workers is not None

    # Whiteboard planner (in examples/whiteboard_planner/workers/whiteboard_planner.yaml)
    whiteboard_registry = WorkerRegistry(examples_dir / "whiteboard_planner")
    planner_def = whiteboard_registry.load_definition("whiteboard_planner")
    assert planner_def.name == "whiteboard_planner"
    assert planner_def.attachment_policy is not None

    # Whiteboard orchestrator (in examples/whiteboard_planner/workers/whiteboard_orchestrator.yaml)
    wb_orchestrator_def = whiteboard_registry.load_definition("whiteboard_orchestrator")
    assert wb_orchestrator_def.name == "whiteboard_orchestrator"
    assert wb_orchestrator_def.allow_workers is not None

    # Calculator (in examples/calculator/workers/calculator/worker.yaml)
    calculator_registry = WorkerRegistry(examples_dir / "calculator")
    calculator_def = calculator_registry.load_definition("calculator")
    assert calculator_def.name == "calculator"

    # Code analyzer (in examples/code_analyzer/workers/code_analyzer/worker.yaml)
    code_analyzer_registry = WorkerRegistry(examples_dir / "code_analyzer")
    code_analyzer_def = code_analyzer_registry.load_definition("code_analyzer")
    assert code_analyzer_def.name == "code_analyzer"

    # Web research agent (in examples/web_research_agent/workers/)
    web_research_registry = WorkerRegistry(examples_dir / "web_research_agent")
    web_orchestrator_def = web_research_registry.load_definition("web_research_orchestrator")
    assert web_orchestrator_def.name == "web_research_orchestrator"
    web_extractor_def = web_research_registry.load_definition("web_research_extractor")
    assert web_extractor_def.name == "web_research_extractor"
    web_consolidator_def = web_research_registry.load_definition("web_research_consolidator")
    assert web_consolidator_def.name == "web_research_consolidator"
    web_reporter_def = web_research_registry.load_definition("web_research_reporter")
    assert web_reporter_def.name == "web_research_reporter"

    # Bootstrapping example uses built-in worker_bootstrapper (no local workers to test)
    # Generated workers in workers/generated/ are created by LLM and may vary
