"""Integration tests for all example workers using TestModel.

These tests verify that all the example workers in examples/ directory
can be loaded and executed successfully using PydanticAI's TestModel.
This ensures the examples stay working as the codebase evolves.

## Testing Philosophy: CWD Matters

Workers using relative paths (like `./notes` or `./input`) depend on CWD
for correct path resolution.

To match real-world usage:
1. Copy example to tmp_path (for test isolation)
2. Change CWD to the example directory (via monkeypatch.chdir)
3. Now relative paths resolve correctly

This mimics how users actually run the examples:
    cd examples/approvals_demo
    llm-do save_note "My note"

Without changing CWD, relative paths would resolve from the project root,
causing files to be written to the wrong location.
"""
import asyncio
import shutil
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from llm_do import (
    ApprovalController,
    WorkerRegistry,
    run_worker_async,
)
from tests.tool_calling_model import ToolCallingModel


def _run_worker(*args, **kwargs):
    return asyncio.run(run_worker_async(*args, **kwargs))


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
    # Change CWD to example directory so relative paths resolve correctly
    monkeypatch.chdir(example_path)
    return WorkerRegistry(example_path)


@pytest.fixture
def pitchdeck_eval_registry(tmp_path, monkeypatch):
    """Registry for the pitchdeck_eval example."""
    example_path = _copy_example_directory("pitchdeck_eval", tmp_path)
    # Change CWD to example directory so relative paths resolve correctly
    monkeypatch.chdir(example_path)
    return WorkerRegistry(example_path)


@pytest.mark.parametrize("input_data", [
    "Tell me a joke",
    "Hello there!",
    {"message": "structured input"},
])
def test_greeter_example(greeter_registry, input_data):
    """Test the greeter example handles various input types."""
    model = TestModel(call_tools=[], custom_output_text="Response text")

    result = _run_worker(
        registry=greeter_registry,
        worker="main",
        input_data=input_data,
        cli_model=model,
    )

    assert result is not None
    assert result.output is not None


@pytest.mark.parametrize("input_data", [
    {"note": "Test note from integration test"},
    "Plain string note",
])
def test_save_note_example(approvals_demo_registry, tool_calling_model_cls, input_data):
    """Test save_note with dict and string inputs."""
    log_file = Path("notes/activity.log")

    if log_file.exists():
        log_file.unlink()

    note_content = "2025-11-22 14:30 • Test note"
    model = tool_calling_model_cls([
        {"name": "write_file", "args": {"path": "notes/activity.log", "content": note_content}},
    ])

    result = _run_worker(
        registry=approvals_demo_registry,
        worker="save_note",
        input_data=input_data,
        cli_model=model,
        approval_controller=ApprovalController(mode="approve_all"),
    )

    assert result is not None
    assert result.output == "Task completed"
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
        _run_worker(
            registry=approvals_demo_registry,
            worker="save_note",
            input_data="This should be blocked",
            cli_model=model,
            approval_controller=ApprovalController(mode="strict"),
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

    result = _run_worker(
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
        _run_worker(
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
        _run_worker(
            registry=pitchdeck_eval_registry,
            worker="pitch_evaluator",
            input_data="Evaluate these",
            cli_model=None,  # Won't get to model execution
            attachments=[pdf1, pdf2],
        )


def test_pitch_orchestrator_example(pitchdeck_eval_registry):
    """Test the pitch_orchestrator example - multi-worker delegation.

    This tests that:
    - Worker loads with filesystem toolset configuration
    - Worker loads with delegation tool configuration
    - Worker can execute with toolsets configured
    - Delegation setup is correct (doesn't test actual delegation with TestModel)

    Note: The fixture changes CWD to the example directory, so relative
    paths (like ./input and ./evaluations) resolve correctly.
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

    # The directories should already exist (copied from example)
    # but create them if needed
    input_dir.mkdir(exist_ok=True)
    eval_dir.mkdir(exist_ok=True)

    # Create a test PDF in the input directory
    test_pdf = input_dir / "test_deck.pdf"
    test_pdf.write_text("Mock pitch deck PDF", encoding="utf-8")

    result = _run_worker(
        registry=pitchdeck_eval_registry,
        worker="pitch_orchestrator",
        input_data="Evaluate all pitch decks",
        cli_model=model,
        approval_controller=ApprovalController(mode="approve_all"),
    )

    assert result is not None
    assert result.output is not None


def test_pitch_orchestrator_toolsets_configured(pitchdeck_eval_registry):
    """Test that pitch_orchestrator has correct toolsets configuration."""
    definition = pitchdeck_eval_registry.load_definition("pitch_orchestrator")

    # Verify toolsets are configured
    assert definition.toolsets is not None
    assert "delegation" in definition.toolsets
    assert "filesystem" in definition.toolsets

    # Verify delegation exposes the expected worker tool
    assert "pitch_evaluator" in definition.toolsets["delegation"]

def test_all_example_workers_load_successfully():
    """Test that all example worker definitions can be loaded.

    This is a smoke test to catch any YAML syntax errors or
    missing required fields in the example worker definitions.
    """
    examples_dir = Path(__file__).parent.parent / "examples"

    # Greeter (in examples/greeter/main.worker)
    greeter_registry = WorkerRegistry(examples_dir / "greeter")
    greeter_def = greeter_registry.load_definition("main")
    assert greeter_def.name == "main"
    assert greeter_def.description is not None

    # Save note (in examples/approvals_demo/workers/save_note.worker)
    approvals_registry = WorkerRegistry(examples_dir / "approvals_demo")
    save_note_def = approvals_registry.load_definition("save_note")
    assert save_note_def.name == "save_note"
    assert save_note_def.toolsets is not None
    assert "filesystem" in save_note_def.toolsets

    # Pitch evaluator (in examples/pitchdeck_eval/workers/pitch_evaluator.worker)
    pitch_registry = WorkerRegistry(examples_dir / "pitchdeck_eval")
    evaluator_def = pitch_registry.load_definition("pitch_evaluator")
    assert evaluator_def.name == "pitch_evaluator"
    assert evaluator_def.attachment_policy is not None

    # Pitch orchestrator (in examples/pitchdeck_eval/workers/pitch_orchestrator.worker)
    orchestrator_def = pitch_registry.load_definition("pitch_orchestrator")
    assert orchestrator_def.name == "pitch_orchestrator"
    assert orchestrator_def.toolsets is not None
    assert "delegation" in orchestrator_def.toolsets
    assert "pitch_evaluator" in orchestrator_def.toolsets["delegation"]

    # Whiteboard planner (in examples/whiteboard_planner/workers/whiteboard_planner.worker)
    whiteboard_registry = WorkerRegistry(examples_dir / "whiteboard_planner")
    planner_def = whiteboard_registry.load_definition("whiteboard_planner")
    assert planner_def.name == "whiteboard_planner"
    assert planner_def.attachment_policy is not None

    # Whiteboard orchestrator (in examples/whiteboard_planner/main.worker)
    wb_orchestrator_def = whiteboard_registry.load_definition("main")
    assert wb_orchestrator_def.name == "main"
    assert wb_orchestrator_def.toolsets is not None
    assert "delegation" in wb_orchestrator_def.toolsets
    assert "whiteboard_planner" in wb_orchestrator_def.toolsets["delegation"]

    # Calculator (in examples/calculator/main.worker)
    calculator_registry = WorkerRegistry(examples_dir / "calculator")
    calculator_def = calculator_registry.load_definition("main")
    assert calculator_def.name == "main"

    # Code analyzer (in examples/code_analyzer/workers/code_analyzer/worker.worker)
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
    # Generated workers go to /tmp/llm-do/generated/ and are session-scoped
