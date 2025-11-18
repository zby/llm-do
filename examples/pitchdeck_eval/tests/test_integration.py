"""Integration tests for pitchdeck evaluation with mocked LLM"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from llm_do.executor import execute_spec
from examples.pitchdeck_eval.tools import PitchdeckToolbox


class MockToolCallHistory:
    """Helper to track tool calls made during execution"""

    def __init__(self):
        self.calls = []

    def record(self, tool_name, arguments):
        self.calls.append({"tool": tool_name, "arguments": arguments})

    def get_calls_to(self, tool_name):
        return [c for c in self.calls if c["tool"] == tool_name]

    def was_called(self, tool_name):
        return any(c["tool"] == tool_name for c in self.calls)


class TestPitchdeckIntegration:
    """Integration tests with mocked LLM model"""

    @pytest.fixture
    def spec_file(self, pitchdeck_workspace):
        """Create a simplified spec file for testing"""
        spec_path = pitchdeck_workspace / "SPEC.md"
        spec_path.write_text("""# Pitchdeck Processor Spec

You are an AI assistant that processes pitchdecks.

Available tools: normalize_filename, run_bash, read_file, write_file

When user says "process pitchdecks":
1. Find PDFs in pipeline/
2. Normalize filenames to get company names
3. Create portfolio directories
4. Move PDFs to portfolio
5. Read framework
6. Create evaluation files
""")
        return spec_path

    def test_toolbox_with_mock_llm_simple(
        self, pitchdeck_workspace, pitchdeck_toolbox, spec_file
    ):
        """Test that toolbox integrates with mocked LLM model"""

        # Create a mock model that simulates LLM behavior
        mock_model = Mock()

        # Mock the chain method to return simulated tool calls and responses
        def mock_chain(*args, **kwargs):
            # Simulate LLM making tool calls
            response = [
                "I'll process the pitchdecks.\n",
                "First, let me find PDF files.\n",
                "Found 2 PDF files to process.\n",
                "Processing complete!\n",
            ]
            return iter(response)

        mock_model.chain = Mock(side_effect=mock_chain)

        # Execute with mocked model
        with patch('llm.get_model', return_value=mock_model):
            with patch('llm.get_default_model', return_value='test-model'):
                result = execute_spec(
                    task="process pitchdecks",
                    spec_path=str(spec_file),
                    toolbox=pitchdeck_toolbox,
                    verbose=False,
                    working_dir=pitchdeck_workspace,
                )

                # Verify model.chain was called
                assert mock_model.chain.called

                # Verify toolbox was passed to chain
                call_kwargs = mock_model.chain.call_args.kwargs
                assert 'tools' in call_kwargs
                assert pitchdeck_toolbox in call_kwargs['tools']

    def test_mock_llm_performs_workflow_steps(
        self, pitchdeck_workspace, sample_pdf_files, spec_file
    ):
        """Test full workflow with LLM making actual tool calls"""

        toolbox = PitchdeckToolbox(working_dir=pitchdeck_workspace)

        # Track which tools the LLM would call
        tool_call_history = MockToolCallHistory()

        # Create a more realistic mock that simulates tool usage
        def mock_chain_with_tools(*args, **kwargs):
            """Simulate LLM making tool calls during processing"""

            # Simulate finding PDFs
            bash_result = toolbox.run_bash("find pipeline/ -name '*.pdf'")
            tool_call_history.record("run_bash", {"command": "find pipeline/ -name '*.pdf'"})

            # Get PDF filenames from result
            pdf_files = [line for line in bash_result.split('\n') if line.strip()]

            # Process each PDF
            for pdf_path in pdf_files:
                if not pdf_path:
                    continue

                filename = Path(pdf_path).name

                # Normalize filename
                company_name = toolbox.normalize_filename(filename)
                tool_call_history.record("normalize_filename", {"filename": filename})

                # Create directory
                toolbox.run_bash(f"mkdir -p portfolio/{company_name}")
                tool_call_history.record(
                    "run_bash", {"command": f"mkdir -p portfolio/{company_name}"}
                )

                # Read framework
                framework = toolbox.read_file("framework/eval_pitchdeck.md")
                tool_call_history.record(
                    "read_file", {"path": "framework/eval_pitchdeck.md"}
                )

                # Create evaluation
                evaluation = f"# Evaluation for {company_name}\n\nBased on framework:\n{framework[:100]}..."
                eval_path = f"portfolio/{company_name}/{company_name}-Evaluation.md"
                toolbox.write_file(eval_path, evaluation)
                tool_call_history.record("write_file", {"path": eval_path})

            response = [
                "Processed 2 pitchdecks successfully.\n",
                f"Companies evaluated: {', '.join([toolbox.normalize_filename(Path(p).name) for p in pdf_files if p])}\n",
            ]
            return iter(response)

        mock_model = Mock()
        mock_model.chain = Mock(side_effect=mock_chain_with_tools)

        # Execute workflow
        with patch('llm.get_model', return_value=mock_model):
            with patch('llm.get_default_model', return_value='test-model'):
                result = execute_spec(
                    task="process pitchdecks in pipeline/",
                    spec_path=str(spec_file),
                    toolbox=toolbox,
                    verbose=False,
                    working_dir=pitchdeck_workspace,
                )

        # Verify workflow steps were executed
        assert tool_call_history.was_called("run_bash")
        assert tool_call_history.was_called("normalize_filename")
        assert tool_call_history.was_called("read_file")
        assert tool_call_history.was_called("write_file")

        # Verify specific calls
        normalize_calls = tool_call_history.get_calls_to("normalize_filename")
        assert len(normalize_calls) == 2  # Two PDF files

        write_calls = tool_call_history.get_calls_to("write_file")
        assert len(write_calls) == 2  # Two evaluation files

        # Verify portfolio directories were created
        company1 = pitchdeck_workspace / "portfolio" / "StartupOneYCS24"
        company2 = pitchdeck_workspace / "portfolio" / "CompanyTwo-Deck"
        assert company1.exists()
        assert company2.exists()

        # Verify evaluation files were created
        eval1 = company1 / "StartupOneYCS24-Evaluation.md"
        eval2 = company2 / "CompanyTwo-Deck-Evaluation.md"
        assert eval1.exists()
        assert eval2.exists()

        # Verify evaluation content
        eval1_content = eval1.read_text()
        assert "Evaluation for StartupOneYCS24" in eval1_content
        assert "Evaluation Areas" in eval1_content  # From framework

    def test_mock_llm_with_approval_callback(
        self, pitchdeck_workspace, sample_pdf_files, spec_file
    ):
        """Test workflow with tool approval enabled"""

        toolbox = PitchdeckToolbox(working_dir=pitchdeck_workspace)

        # Create simple mock that returns immediately
        mock_model = Mock()
        mock_model.chain = Mock(return_value=iter(["Test response"]))

        # Execute with tools_approve=True
        with patch('llm.get_model', return_value=mock_model):
            with patch('llm.get_default_model', return_value='test-model'):
                result = execute_spec(
                    task="test task",
                    spec_path=str(spec_file),
                    toolbox=toolbox,
                    verbose=False,
                    working_dir=pitchdeck_workspace,
                    tools_approve=True,
                )

                # Verify before_call callback was provided
                call_kwargs = mock_model.chain.call_args.kwargs
                assert 'before_call' in call_kwargs
                assert call_kwargs['before_call'] is not None

    def test_normalize_filename_consistency(self, pitchdeck_toolbox):
        """Test that normalize_filename produces consistent results"""

        test_cases = [
            ("Real Research (YC S24).pdf", "RealResearchYCS24"),
            ("Startup Name - Deck.pdf", "StartupName-Deck"),
            ("Company (Batch 2024).pdf", "CompanyBatch2024"),
        ]

        for input_name, expected_output in test_cases:
            result = pitchdeck_toolbox.normalize_filename(input_name)
            assert result == expected_output, (
                f"normalize_filename('{input_name}') returned '{result}', "
                f"expected '{expected_output}'"
            )

    def test_framework_file_exists_and_readable(
        self, pitchdeck_toolbox, pitchdeck_workspace
    ):
        """Test that framework file can be read by toolbox"""

        content = pitchdeck_toolbox.read_file("framework/eval_pitchdeck.md")

        # Verify framework has expected structure
        assert "Evaluation Areas" in content
        assert "Problem & Solution" in content
        assert "Market Opportunity" in content
        assert "Team" in content

    def test_multiple_pdfs_processed_independently(
        self, pitchdeck_workspace, sample_pdf_files, pitchdeck_toolbox
    ):
        """Test that multiple PDFs are processed independently"""

        companies_processed = []

        for pdf_file in sample_pdf_files:
            filename = pdf_file.name
            company_name = pitchdeck_toolbox.normalize_filename(filename)

            # Create directory
            pitchdeck_toolbox.run_bash(f"mkdir -p portfolio/{company_name}")

            # Write evaluation
            eval_content = f"# Evaluation for {company_name}\n\nTest evaluation"
            pitchdeck_toolbox.write_file(
                f"portfolio/{company_name}/{company_name}-Evaluation.md",
                eval_content,
            )

            companies_processed.append(company_name)

        # Verify both companies were processed
        assert len(companies_processed) == 2
        assert "StartupOneYCS24" in companies_processed
        assert "CompanyTwo-Deck" in companies_processed

        # Verify each has its own directory and evaluation
        for company_name in companies_processed:
            company_dir = pitchdeck_workspace / "portfolio" / company_name
            assert company_dir.exists()

            eval_file = company_dir / f"{company_name}-Evaluation.md"
            assert eval_file.exists()

            eval_content = eval_file.read_text()
            assert company_name in eval_content


class TestWorkflowErrorHandling:
    """Test error handling in workflows"""

    def test_handles_missing_framework_gracefully(
        self, pitchdeck_workspace, pitchdeck_toolbox
    ):
        """Test that missing framework file returns error message"""

        # Try to read non-existent file
        result = pitchdeck_toolbox.read_file("framework/nonexistent.md")

        # Should return error message, not crash
        assert "Error reading" in result or "not found" in result.lower()

    def test_handles_invalid_bash_command(self, pitchdeck_toolbox):
        """Test that invalid bash commands return error"""

        result = pitchdeck_toolbox.run_bash("false")  # Command that returns exit code 1

        # Should indicate error
        assert "Error" in result or "exit 1" in result

    def test_normalize_filename_handles_edge_cases(self, pitchdeck_toolbox):
        """Test normalize_filename with edge cases"""

        # Test with no extension
        result = pitchdeck_toolbox.normalize_filename("CompanyName")
        assert result == "CompanyName"

        # Test with only special characters
        result = pitchdeck_toolbox.normalize_filename("@#$%.pdf")
        assert isinstance(result, str)  # Should not crash

        # Test with empty string (if that ever happens)
        result = pitchdeck_toolbox.normalize_filename("")
        assert isinstance(result, str)
