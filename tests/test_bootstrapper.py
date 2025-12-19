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
    """Integration test: bootstrapper lists files, creates worker, delegates, writes output."""
    mock_evaluation = "# Evaluation\n\nStrengths: Clear. Weaknesses: Limited."

    # Sequence: list_files → worker_create → worker_call → write_file
    model = SequentialToolCallingModel(
        tool_sequence=[
            {"name": "list_files", "args": {"path": "input"}},
            {"name": "worker_create", "args": {
                "name": "pitch_deck_analyzer",
                "description": "Analyzes pitch decks",
                "instructions": "Analyze the pitch deck.",
            }},
            {"name": "worker_call", "args": {
                "worker": "pitch_deck_analyzer",
                "attachments": ["input/test_pitch.pdf"],
            }},
            {"name": "write_file", "args": {
                "path": "output/test_pitch_evaluation.md",
                "content": mock_evaluation,
            }},
        ],
        final_text="Done",
    )

    # Mock nested worker call
    async def mock_call_worker(**kwargs):
        return WorkerRunResult(output=mock_evaluation, messages=[])

    monkeypatch.setattr(llm_do.runtime, "call_worker_async", mock_call_worker)

    result = asyncio.run(
        run_worker_async(
            registry=bootstrapper_registry,
            worker="worker_bootstrapper",
            input_data="Analyze pitch decks",
            cli_model=model,
            approval_controller=ApprovalController(mode="approve_all"),
        )
    )

    assert result is not None
    assert Path("output/test_pitch_evaluation.md").exists()
    assert (bootstrapper_registry.generated_dir / "pitch_deck_analyzer" / "worker.worker").exists()


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
    """Test that bootstrapper can write to output directory."""
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
