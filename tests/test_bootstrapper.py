"""Functional tests for the worker_bootstrapper.

Tests the bootstrapper's ability to:
1. List input files
2. Create a specialized worker dynamically
3. Delegate work to the created worker
4. Write results to output
"""
import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import Model

import llm_do.runtime
from llm_do import ApprovalController, WorkerRegistry, WorkerRunResult, run_worker_async


class SequentialToolCallingModel(Model):
    """Mock model that emits tool calls one at a time, simulating realistic LLM behavior.

    Unlike ToolCallingModel which emits all calls at once, this model:
    1. Emits one tool call per turn
    2. Waits for the tool result before making the next call
    3. Returns final text after all tools are called
    """

    def __init__(self, tool_sequence: list[dict[str, Any]], final_text: str = "Done"):
        super().__init__()
        self.tool_sequence = tool_sequence
        self.final_text = final_text
        self.current_index = 0

    @property
    def model_name(self) -> str:
        return "sequential-tool-mock"

    @property
    def system(self) -> str:
        return "test"

    async def request(self, messages, model_settings, model_request_parameters):
        # Check if we have more tool calls to make
        if self.current_index < len(self.tool_sequence):
            call = self.tool_sequence[self.current_index]
            self.current_index += 1

            # Build parts: optional text prefix + tool call
            parts = []
            if "text" in call:
                parts.append(TextPart(content=call["text"]))

            parts.append(
                ToolCallPart(
                    tool_name=call["name"],
                    args=call["args"],
                    tool_call_id=f"call_{self.current_index}",
                )
            )
            return ModelResponse(parts=parts, model_name=self.model_name)

        # All tools called, return final response
        return ModelResponse(
            parts=[TextPart(content=self.final_text)],
            model_name=self.model_name,
        )


@pytest.fixture
def bootstrapper_registry(tmp_path, monkeypatch):
    """Registry with bootstrapper and input/output directories."""
    dest = tmp_path / "bootstrapping_test"
    dest.mkdir()

    # Create input directory with a test PDF
    input_dir = dest / "input"
    input_dir.mkdir()
    (input_dir / "test_pitch.pdf").write_bytes(b"%PDF-1.4 fake pdf content")

    # Create output directory
    (dest / "output").mkdir()

    # Use test-specific generated directory (not global /tmp/llm-do/generated)
    generated_dir = dest / "generated"
    generated_dir.mkdir()

    monkeypatch.chdir(dest)
    return WorkerRegistry(dest, generated_dir=generated_dir)


def test_bootstrapper_pitchdeck_workflow(bootstrapper_registry, monkeypatch):
    """Test the complete bootstrapper workflow for pitch deck analysis.

    Simulates the real execution:
    1. list_files("input") → finds test_pitch.pdf
    2. worker_create() → creates pitch_deck_analyzer
    3. worker_call() → delegates to analyzer (mocked)
    4. write_file() → saves evaluation
    """
    # The evaluation that the nested worker would return
    mock_evaluation = """# Test Pitch Evaluation

## Strengths
- Clear problem statement
- Strong team background

## Weaknesses
- Limited financial projections

## Overall
Moderate investor interest likely.
"""

    # Define the sequential tool calls the bootstrapper should make
    bootstrapper_model = SequentialToolCallingModel(
        tool_sequence=[
            # Step 1: List input files
            {
                "text": "Let me find the pitch decks in the input directory.",
                "name": "list_files",
                "args": {"path": "input"},
            },
            # Step 2: Create analyzer worker
            {
                "text": "Found a pitch deck. Creating a specialized analyzer worker.",
                "name": "worker_create",
                "args": {
                    "name": "pitch_deck_analyzer",
                    "description": "Analyzes pitch decks",
                    "instructions": "Analyze the pitch deck and provide evaluation.",
                },
            },
            # Step 3: Call the analyzer
            {
                "text": "Now analyzing the pitch deck.",
                "name": "worker_call",
                "args": {
                    "worker": "pitch_deck_analyzer",
                    "attachments": ["input/test_pitch.pdf"],
                },
            },
            # Step 4: Write the result
            {
                "text": "Saving the evaluation.",
                "name": "write_file",
                "args": {
                    "path": "output/test_pitch_evaluation.md",
                    "content": mock_evaluation,
                },
            },
        ],
        final_text="Analysis complete. Saved to output/test_pitch_evaluation.md",
    )

    # Mock the nested worker call to return our evaluation
    async def mock_call_worker_async(**kwargs):
        assert kwargs["worker"] == "pitch_deck_analyzer"
        assert "test_pitch.pdf" in str(kwargs.get("attachments", []))
        return WorkerRunResult(output=mock_evaluation, messages=[])

    original_call = llm_do.runtime.call_worker_async
    monkeypatch.setattr(llm_do.runtime, "call_worker_async", mock_call_worker_async)

    try:
        result = asyncio.run(
            run_worker_async(
                registry=bootstrapper_registry,
                worker="worker_bootstrapper",
                input_data="Analyze pitch decks and save evaluations",
                cli_model=bootstrapper_model,
                approval_controller=ApprovalController(mode="approve_all"),
            )
        )

        assert result is not None
        assert "complete" in result.output.lower()

        # Verify the output file was created
        output_file = Path("output/test_pitch_evaluation.md")
        assert output_file.exists()
        content = output_file.read_text()
        assert "Strengths" in content
        assert "Weaknesses" in content

        # Verify the worker was created in the registry's generated directory
        # Generated workers are directories: {name}/worker.worker
        worker_file = bootstrapper_registry.generated_dir / "pitch_deck_analyzer" / "worker.worker"
        assert worker_file.exists()

    finally:
        monkeypatch.setattr(llm_do.runtime, "call_worker_async", original_call)


def test_bootstrapper_lists_files_correctly(bootstrapper_registry):
    """Test that bootstrapper can list files without creating workers."""
    model = SequentialToolCallingModel(
        tool_sequence=[
            {
                "name": "list_files",
                "args": {"path": "input"},
            },
        ],
        final_text="Found 1 file: test_pitch.pdf",
    )

    result = asyncio.run(
        run_worker_async(
            registry=bootstrapper_registry,
            worker="worker_bootstrapper",
            input_data="List files in input",
            cli_model=model,
            approval_controller=ApprovalController(mode="approve_all"),
        )
    )

    assert result is not None
    assert "test_pitch.pdf" in result.output or "1 file" in result.output


def test_bootstrapper_creates_worker(bootstrapper_registry):
    """Test that bootstrapper can create a new worker."""
    model = SequentialToolCallingModel(
        tool_sequence=[
            {
                "name": "worker_create",
                "args": {
                    "name": "test_analyzer",
                    "description": "Test worker",
                    "instructions": "You are a test analyzer.",
                },
            },
        ],
        final_text="Created worker: test_analyzer",
    )

    result = asyncio.run(
        run_worker_async(
            registry=bootstrapper_registry,
            worker="worker_bootstrapper",
            input_data="Create a test analyzer worker",
            cli_model=model,
            approval_controller=ApprovalController(mode="approve_all"),
        )
    )

    assert result is not None

    # Verify the worker file was created in registry's generated directory
    # Generated workers are directories: {name}/worker.worker
    worker_file = bootstrapper_registry.generated_dir / "test_analyzer" / "worker.worker"
    assert worker_file.exists()

    # Verify content
    content = worker_file.read_text()
    assert "test_analyzer" in content
    assert "Test worker" in content


def test_bootstrapper_writes_output(bootstrapper_registry):
    """Test that bootstrapper can write to output sandbox."""
    test_content = "# Test Output\n\nThis is a test."

    model = SequentialToolCallingModel(
        tool_sequence=[
            {
                "name": "write_file",
                "args": {
                    "path": "output/test_output.md",
                    "content": test_content,
                },
            },
        ],
        final_text="Wrote output file.",
    )

    result = asyncio.run(
        run_worker_async(
            registry=bootstrapper_registry,
            worker="worker_bootstrapper",
            input_data="Write a test file",
            cli_model=model,
            approval_controller=ApprovalController(mode="approve_all"),
        )
    )

    assert result is not None

    # Verify the output file was created
    output_file = Path("output/test_output.md")
    assert output_file.exists()
    assert output_file.read_text() == test_content
